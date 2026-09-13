"""Structural reproductions, not a reconstruction of the unrecorded live mismatch."""

import asyncio
import json
import os
from uuid import uuid4

import pytest
from pydantic import ValidationError

from executors.ascend_extension.board_schema import BoardSchemaDiagnostic
from executors.ascend_extension.runtime_contracts import RuntimeBoardEvidence
from tests.test_ascend_x1_controller import repo as repo, session, view_contract
from tests.test_ascend_x1_dom import EXT, markup
from tests.test_ascend_x1_runtime import board, cycle, result, runtime as runtime, wake


def diagnostic(predicate="ROW_CELL_COUNT_MISMATCH"):
    return dict(version=1, candidate_grid_count=0, candidates=[], failed_predicate=predicate, metadata_truncated=False,
                selected_candidate=None, render_samples=2,
                pagination=dict(page_size=None, next_disabled=None, previous_disabled=None))


def board_dispatch(controller):
    controller.finish(result(wake(controller), session()))
    controller.finish(result(wake(controller), {"view_contract": view_contract()}))
    return wake(controller)


def test_failed_schema_cannot_be_promoted_by_success_envelope():
    with pytest.raises(ValidationError):
        RuntimeBoardEvidence.model_validate({**board(), "schema_diagnostic": diagnostic()})


def test_safe_schema_predicate_persisted_without_changing_retained_board(runtime):
    access, controller, now, *_ = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    before = access.status()
    now[0] += 301
    response = controller.finish(result(board_dispatch(controller), {
        "view_contract": view_contract(), "schema_diagnostic": diagnostic(),
    }, "BOARD_SCHEMA_INVALID"))
    status = response["status"]
    assert status["schema_predicate"] == "ROW_CELL_COUNT_MISMATCH"
    assert status["board_schema_diagnostic"] == diagnostic()
    assert status["board_evidence_status"] == "LAST_KNOWN_BOARD_EVIDENCE"
    for name in ("load_count", "board_hash", "last_board_sync"):
        assert status[name] == before[name]
    with access.database(readonly=True) as db:
        receipts = [json.loads(r[0]) for r in db.execute("SELECT body FROM runtime_receipts")]
        events = [json.loads(r[0]) for r in db.execute("SELECT body FROM runtime_events")]
        assert db.execute("SELECT COUNT(*) FROM runtime_proposals").fetchone()[0] == 1
    assert any(r.get("schema_predicate") == "ROW_CELL_COUNT_MISMATCH" for r in receipts)
    assert any(e.get("schema_predicate") == "ROW_CELL_COUNT_MISMATCH" for e in events)


@pytest.mark.parametrize("bad", [None, {**diagnostic(), "failed_predicate": "PRIVATE_SECRET"},
                                 {**diagnostic(), "raw_html": "PRIVATE_SECRET"}])
def test_absent_or_untrusted_diagnostic_never_persists_private_values(runtime, bad):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    evidence = {"view_contract": view_contract()}
    if bad is not None:
        evidence["schema_diagnostic"] = bad
    status = controller.finish(result(board_dispatch(controller), evidence, "BOARD_SCHEMA_INVALID"))["status"]
    assert status["schema_predicate"] == "STRUCTURAL_METADATA_UNAVAILABLE"
    with access.database(readonly=True) as db:
        for table in ("runtime_state", "runtime_events", "runtime_receipts"):
            assert "PRIVATE_SECRET" not in str(db.execute(f"SELECT * FROM {table}").fetchall())


@pytest.mark.parametrize("kind,predicate", [("hash", "HOST_BOARD_HASH_MISMATCH"),
                                           ("duplicate", "HOST_DUPLICATE_LOAD_ID")])
def test_host_schema_failures_have_precise_predicates(runtime, kind, predicate):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    payload = board() if kind == "hash" else board(("42", "42"))
    payload["board_hash"] = "a" * 64
    status = controller.finish(result(board_dispatch(controller), payload))["status"]
    assert status["schema_predicate"] == predicate
    assert status["load_count"] is None


def test_structural_grid_selection_alignment_and_rendering_offline(tmp_path):
    async def run():
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                str(tmp_path / "schema-fixture-profile"), channel="msedge", headless=True,
                service_workers="block", env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
            )
            # No request reaches Ascend or any other site. Never use the live profile.
            await context.route("**/*", lambda r: r.fulfill(content_type="text/html", body="<title>Offline fixture</title>"))
            try:
                page = await context.new_page()
                await page.goto("https://ascendtms.com/loads")

                async def run_case(change="", *, runtime_read=False):
                    await page.set_content(markup())
                    for file in ("contract.js", "read-errors.js", "load-board-view.js", "reader.js"):
                        await page.add_script_tag(path=str(EXT / file))
                    await page.evaluate("""async change=>{
                        window.reader=await FreightDeskX1Reader.create(document,location.origin);
                        for(const row of document.querySelectorAll('tbody tr'))for(const [i,cell] of [...row.children].entries())
                            if(![0,5,7].includes(i))Object.defineProperty(cell,'textContent',{get(){throw Error('PRIVATE_FIELD_READ_FORBIDDEN');}});
                        new Function(change)();
                    }""", change)
                    command = dict(version=1, request_id=uuid4().hex, operation="ASCEND_GET_ACTIVE_LOADS",
                                   load_id=None, expected_revision=None, tenant_id="booking-logistics", actor="FreightDesk/Avery")
                    response = await page.evaluate("""async ({command,runtime_read})=>{
                        try{return {ok:true,evidence:await reader[runtime_read?'executeRuntime':'executeIdentity'](command,()=>{}),diagnostic:reader.boardDiagnostic()};}
                        catch(error){return {ok:false,error_code:FreightDeskReadErrors.safe(error),diagnostic:reader.boardDiagnostic()};}
                    }""", dict(command=command, runtime_read=runtime_read))
                    assert "PRIVATE" not in json.dumps(response)
                    BoardSchemaDiagnostic.model_validate(response["diagnostic"])
                    if response["ok"] and runtime_read:
                        RuntimeBoardEvidence.model_validate(response["evidence"])
                    return response

                baseline = await run_case(runtime_read=True)
                assert baseline["ok"] and baseline["diagnostic"]["render_samples"] >= 2
                for place in ("before", "after"):
                    value = await run_case(f"const t=document.querySelector('table'),c=t.cloneNode(true);c.querySelector('tbody').replaceChildren();t.{place}(c);", runtime_read=True)
                    assert value["ok"] and value["evidence"]["board_hash"] == baseline["evidence"]["board_hash"]
                    assert value["diagnostic"]["candidate_grid_count"] == 2
                    assert sum(c["data_bearing"] for c in value["diagnostic"]["candidates"]) == 1

                # Column relocation and normalization are accepted only with the full semantic schema.
                value = await run_case("""for(const row of document.querySelectorAll('tr'))row.append(row.firstElementChild);
                    for(const h of document.querySelectorAll('th'))h.textContent='  '+h.textContent.toLowerCase()+'  ';""", runtime_read=True)
                assert value["ok"] and value["evidence"]["board_hash"] == baseline["evidence"]["board_hash"]
                assert value["diagnostic"]["candidates"][0]["required_header_mapping"]["Load ID"] == 32
                revision = value["evidence"]["board_hash"]
                await page.evaluate("""()=>document.getElementById('open-1755').onclick=e=>{
                    e.preventDefault();const d=document.createElement('div');d.id='detail';d.setAttribute('role','dialog');d.innerHTML='<h2>Load # 1755</h2>';document.body.append(d);
                }""")
                for operation in ("ASCEND_FIND_LOAD", "ASCEND_OPEN_LOAD_READONLY"):
                    evidence = await page.evaluate("""async c=>reader.executeRuntime(c,()=>{})""", dict(
                        version=1, request_id=uuid4().hex, operation=operation, load_id="1755",
                        expected_revision=revision, tenant_id="booking-logistics", actor="FreightDesk/Avery"))
                    assert evidence

                value = await run_case("for(const r of document.querySelectorAll('tr'))r.children[3].style.display='none';")
                assert value["ok"]
                assert value["diagnostic"]["candidates"][0]["row_visible_cell_counts"] == [32]
                assert value["diagnostic"]["candidates"][0]["row_cell_counts"] == [33]

                cases = [
                    ("document.querySelector('table').after(document.querySelector('table').cloneNode(true));", "AMBIGUOUS_DATA_GRIDS"),
                    ("document.querySelector('thead tr').lastElementChild.remove();", "HEADER_COUNT_MISMATCH"),
                    ("document.querySelector('tbody tr').lastElementChild.remove();", "ROW_CELL_COUNT_MISMATCH"),
                    ("document.querySelectorAll('th')[5].textContent='PRIVATE_UNKNOWN_HEADER';", "REQUIRED_HEADERS_MISSING"),
                    ("document.querySelectorAll('th')[3].textContent='Carrier';", "DUPLICATE_REQUIRED_HEADERS"),
                    ("document.querySelector('th').colSpan=2;", "HEADER_SPAN"),
                    ("document.querySelector('td').rowSpan=2;", "ROW_SPAN"),
                    ("document.querySelector('td').setAttribute('aria-colindex','2');", "ARIA_COLUMN_ALIGNMENT"),
                    ("document.querySelector('tbody').replaceChildren();", "EMPTY_STATE_UNVERIFIED"),
                    ("document.querySelector('table').setAttribute('aria-busy','true');", "INITIALIZATION_BUSY"),
                    ("document.querySelector('table').style.display='none';", "NO_VISIBLE_GRID"),
                    ("document.querySelector('td').textContent='not-an-id';", "ROW_IDENTITY_INVALID"),
                    ("document.querySelectorAll('tbody tr')[1].firstElementChild.textContent='1755';", "DUPLICATE_LOAD_ID"),
                ]
                for change, predicate in cases:
                    value = await run_case(change)
                    assert not value["ok"] and value["error_code"] == "BOARD_SCHEMA_INVALID", predicate
                    assert value["diagnostic"]["failed_predicate"] == predicate
                raw = value["diagnostic"]
                raw["candidates"][0]["header_labels"][0] = "PRIVATE_HEADER"
                with pytest.raises(ValidationError):
                    BoardSchemaDiagnostic.model_validate(raw)

                value = await run_case("""const t=document.querySelector('table');t.setAttribute('aria-busy','true');
                    setTimeout(()=>t.removeAttribute('aria-busy'),350);""", runtime_read=True)
                assert value["ok"] and value["diagnostic"]["render_samples"] >= 3
                value = await run_case("""const c=document.querySelector('tbody tr').lastElementChild,p=c.parentElement;c.remove();
                    setTimeout(()=>p.append(c),350);""", runtime_read=True)
                assert value["ok"]
                value = await run_case("document.querySelector('tbody tr').lastElementChild.remove();", runtime_read=True)
                assert not value["ok"] and value["diagnostic"]["failed_predicate"] == "ROW_CELL_COUNT_MISMATCH"
                assert value["diagnostic"]["render_samples"] > 2

                value = await run_case("""const t=document.querySelector('table'),w=document.createElement('div');w.className='dataTables_wrapper';
                    t.before(w);w.append(t);w.insertAdjacentHTML('beforeend','<select name=loads_length><option selected>100</option></select><a class="paginate_button next disabled"></a><a class="paginate_button previous disabled"></a>');
                    document.querySelector('tbody tr').lastElementChild.remove();""")
                assert value["diagnostic"]["pagination"] == dict(page_size=100, next_disabled=True, previous_disabled=True)
                value = await run_case("""const t=document.querySelector('table');
                    for(let i=0;i<29;i++)t.after(t.cloneNode(true));""")
                assert value["diagnostic"]["failed_predicate"] == "AMBIGUOUS_DATA_GRIDS"
                assert value["diagnostic"]["candidate_grid_count"] == 30
                assert len(json.dumps(value["diagnostic"], separators=(',', ':')).encode()) <= 30000
                assert value["diagnostic"]["metadata_truncated"]
            finally:
                await context.close()

    asyncio.run(run())
