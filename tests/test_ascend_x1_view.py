"""Provider-view contract fixtures only; no live browser/profile, grant or pairing operation."""

import asyncio
import json
import os
from uuid import uuid4

import pytest

from executors.ascend_extension.contracts import ReadCommand
from executors.ascend_extension.controller import ReadController
from executors.ascend_extension.controller import prepare
from executors.ascend_extension.view_contract import AscendLoadBoardViewContract
from tests.test_ascend_x1_controller import board, release, request, result, session, view_contract
from tests.test_ascend_x1_controller import repo as repo
from tests.test_ascend_x1_controller import PICKUPS, DELIVERIES
from tests.test_ascend_x1_dom import EXT, markup


def test_provider_view_dom_cases_and_changed_view_stop(tmp_path):
    async def run():
        from playwright.async_api import async_playwright

        controls = '<div role="tablist"><button id="active" role="tab" {a}>Active Loads</button><button id="all" role="tab" {b}>All Loads</button></div>'
        cases = [
            (
                "active_selected",
                controls.format(a='aria-selected="true"', b='aria-selected="false"'),
                "ACTIVE_LOADS",
            ),
            (
                "all_selected",
                controls.format(a='aria-selected="false"', b='aria-selected="true"'),
                "ALL_LOADS",
            ),
            (
                "one_aria",
                controls.format(a='aria-selected="true"', b="") + "<button>Ready for Accounting</button>",
                "ACTIVE_LOADS",
            ),
            ("css_control", controls.format(a='class="active PRIVATE_TOKEN"', b=""), "ACTIVE_LOADS"),
            ("aria_current_true", controls.format(a='aria-current="true"', b=""), "ACTIVE_LOADS"),
            (
                "accessible_label",
                '<button aria-label="Active Loads" aria-selected="true"><span>Icon</span></button>',
                "ACTIVE_LOADS",
            ),
            (
                "css_parent",
                '<ul class="nav-tabs"><li class="active PRIVATE"><a>Active Loads</a></li><li><a>All Loads</a></li></ul>',
                "ACTIVE_LOADS",
            ),
            (
                "title",
                "<main><h1>Active Loads</h1>" + controls.format(a="", b="") + "</main>",
                "ACTIVE_LOADS",
            ),
            (
                "accounting",
                '<button aria-pressed="true">Ready for Accounting</button>',
                "READY_FOR_ACCOUNTING",
            ),
            ("ambiguous", controls.format(a='aria-selected="true"', b='aria-selected="true"'), "UNKNOWN"),
            ("no_state", controls.format(a="", b=""), "UNKNOWN"),
            ("path_only", "<p>Fixture at /loads</p>", "UNKNOWN"),
            ("counts_only", markup().replace('aria-selected="true"', ""), "UNKNOWN"),
            (
                "other",
                '<div role="tablist"><button>Active Loads</button><button aria-selected="true">PRIVATE_CUSTOMER_VIEW</button></div>',
                "OTHER",
            ),
            (
                "container",
                '<section id="private-container" data-board-view="all_loads"><table><tr><td>PRIVATE_CUSTOMER</td></tr></table></section>',
                "ALL_LOADS",
            ),
            (
                "data_control",
                '<button data-view="active_loads" aria-selected="true"><span aria-hidden="true">&#x2022;</span></button>',
                "ACTIVE_LOADS",
            ),
            (
                "data_conflict",
                '<button data-view="all_loads" aria-selected="true">Active Loads</button>',
                "UNKNOWN",
            ),
            ("state_conflict", controls.format(a='aria-selected="false" class="active"', b=""), "UNKNOWN"),
            (
                "title_conflict",
                "<h1>All Loads</h1>" + controls.format(a='aria-selected="true"', b=""),
                "UNKNOWN",
            ),
            (
                "linked_panel",
                '<div role="tablist"><a href="#a-panel">Active Loads</a><a href="#b-panel">All Loads</a></div><div id="a-panel" role="tabpanel"></div><div id="b-panel" role="tabpanel" hidden></div>',
                "ACTIVE_LOADS",
            ),
            ("single_link_not_proof", '<a href="/loads">Active Loads</a>', "UNKNOWN"),
            (
                "linked_conflict",
                '<a href="#a-panel">Active Loads</a><div id="a-panel" role="tabpanel" data-board-view="all_loads"></div>',
                "UNKNOWN",
            ),
            (
                "shared_parent_not_proof",
                '<li class="active"><a>Active Loads</a><a>All Loads</a></li>',
                "UNKNOWN",
            ),
            (
                "hidden_title",
                "<h1 hidden>All Loads</h1>" + controls.format(a='aria-selected="true"', b=""),
                "ACTIVE_LOADS",
            ),
            ("bound", "<button>Active Loads</button>" * 33, "UNKNOWN"),
        ]
        async with async_playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                str(tmp_path / "fixture-profile"),
                channel="msedge",
                headless=True,
                service_workers="block",
                env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
            )
            await context.route(
                "**/*", lambda r: r.fulfill(content_type="text/html", body="<title>Offline fixture</title>")
            )
            try:
                page = await context.new_page()
                await page.goto("https://ascendtms.com/loads")
                for name, html, view in cases:
                    await page.set_content(html)
                    await page.add_script_tag(path=str(EXT / "load-board-view.js"))
                    if name == "container":
                        await page.evaluate(
                            "() => Object.defineProperty(document.querySelector('#private-container'),'textContent',{get(){throw Error('private container body read');}})"
                        )
                    evidence = await page.evaluate(
                        "()=>FreightDeskLoadBoardView.observe(document).diagnostic"
                    )
                    assert evidence["view"] == view, (name, evidence)
                    assert evidence["confidence"] == ("UNKNOWN" if view == "UNKNOWN" else "VERIFIED"), name
                    contract = AscendLoadBoardViewContract.model_validate(evidence)
                    assert contract.source == "provider DOM"
                    assert "PRIVATE" not in json.dumps(evidence), name
                    assert "load_id" not in json.dumps(evidence)
                # No row values are read if independent view evidence is absent or proves another view.
                for kind in ("unknown", "all", "changed", "transient"):
                    await page.set_content(
                        markup().replace(
                            '<a role="tab" aria-selected="true">Active Loads</a>',
                            controls.format(
                                a='aria-selected="true"' if kind in ("changed", "transient") else "",
                                b='aria-selected="true"' if kind == "all" else "",
                            ),
                        )
                    )
                    for name in ("contract.js", "load-board-view.js", "reader.js", "read-errors.js"):
                        await page.add_script_tag(path=str(EXT / name))
                    await page.evaluate(
                        """kind=>{
                        window.rowReads=0;
                        if(['unknown','all'].includes(kind))for(const cell of document.querySelectorAll('tbody td'))
                            Object.defineProperty(cell,'textContent',{get(){rowReads++;throw Error('private row read before view verified');}});
                    }""",
                        kind,
                    )
                    command = ReadCommand(
                        operation="ASCEND_GET_ACTIVE_LOADS", request_id=uuid4().hex
                    ).model_dump()
                    response = await page.evaluate(
                        """async ({command,kind})=>{
                        const reader=await FreightDeskX1Reader.create(document,location.origin);let calls=0;
                        const lease=()=>{if(++calls===2&&['changed','transient'].includes(kind))queueMicrotask(()=>{
                            document.querySelector('#active').setAttribute('aria-selected','false');
                            document.querySelector('#all').setAttribute('aria-selected','true');
                            if(kind==='transient'){
                                document.querySelector('#active').setAttribute('aria-selected','true');
                                document.querySelector('#all').removeAttribute('aria-selected');
                            }
                        });};
                        try{return {ok:true,evidence:await reader.executeIdentity(command,lease)};}
                        catch(error){return {ok:false,error_code:FreightDeskReadErrors.safe(error),view_contract:reader.viewDiagnostic(),row_reads:rowReads};}
                    }""",
                        {"command": command, "kind": kind},
                    )
                    assert not response["ok"], kind
                    assert (
                        response["error_code"]
                        == {
                            "unknown": "ACTIVE_VIEW_UNVERIFIED",
                            "all": "ACTIVE_VIEW_NOT_ACTIVE_LOADS",
                            "changed": "ACTIVE_VIEW_CHANGED",
                            "transient": "ACTIVE_VIEW_CHANGED",
                        }[kind]
                    ), response
                    AscendLoadBoardViewContract.model_validate(response["view_contract"])
                    if kind in ("unknown", "all"):
                        assert response["row_reads"] == 0
            finally:
                await context.close()

    asyncio.run(run())


@pytest.mark.parametrize("view", ["ALL_LOADS", "READY_FOR_ACCOUNTING", "OTHER"])
def test_host_rejects_other_view_even_with_exact_eleven_rows(repo, view):
    release(repo)
    c = ReadController(repo)
    c.finish(result(c.begin(request(c)), session()))
    data = board()
    data["view_contract"] = view_contract(view)
    dispatch = c.begin(request(c))
    with pytest.raises(PermissionError, match="ACTIVE_VIEW_NOT_ACTIVE_LOADS") as error:
        c.finish(result(dispatch, data))
    receipt = c.fail(error.value)
    assert receipt["view_contract"]["view"] == view
    assert receipt["identity"] == "UNKNOWN" and "rows" not in receipt and "load_ids" not in receipt


@pytest.mark.parametrize(
    "mutation",
    [
        {"view": "ALL_LOADS"},
        {"confidence": "UNKNOWN"},
        {"version": True},
        {"candidate_count": 0},
        {"source": "owner guess"},
        {"raw_html": "PRIVATE"},
        {"candidate_bound_exceeded": True},
    ],
)
def test_view_contract_rejects_inconsistent_or_private_evidence(mutation):
    with pytest.raises(ValueError):
        AscendLoadBoardViewContract.model_validate(view_contract() | mutation)


@pytest.mark.parametrize(
    "field,value",
    [
        ("label", "PRIVATE_CUSTOMER"),
        ("safe_classes", ["PRIVATE_TOKEN"]),
        ("data_view", "PRIVATE"),
        ("aria_selected", 1),
    ],
)
def test_candidate_allowlist_never_accepts_private_values(field, value):
    evidence = view_contract()
    evidence["candidates"][0][field] = value
    with pytest.raises(ValueError):
        AscendLoadBoardViewContract.model_validate(evidence)


@pytest.mark.parametrize(
    "code,view,selected",
    [("ACTIVE_VIEW_UNVERIFIED", "ACTIVE_LOADS", False), ("ACTIVE_VIEW_CHANGED", "ALL_LOADS", True)],
)
def test_view_diagnostic_survives_failed_command_without_private_rows(repo, code, view, selected):
    release(repo)
    c = ReadController(repo)
    c.finish(result(c.begin(request(c)), session()))
    dispatch = c.begin(request(c))
    with pytest.raises(PermissionError, match=code) as error:
        c.finish(result(dispatch, {"view_contract": view_contract(view, selected)}, code))
    receipt = c.fail(error.value)
    assert receipt["view_contract"]["view"] == (view if selected else "UNKNOWN")
    assert receipt["error_code"] == code
    with c.repo.database() as db:
        persisted = json.loads(
            db.execute(
                "SELECT body FROM x1_read_events WHERE request_id=?", (dispatch["command"]["request_id"],)
            ).fetchone()[0]
        )
    assert persisted == receipt and "rows" not in persisted


def test_old_board_receipt_without_provider_view_proof_cannot_pass(repo):
    release(repo)
    c = ReadController(repo)
    c.finish(result(c.begin(request(c)), session()))
    data = board()
    del data["view_contract"]
    with pytest.raises(ValueError):
        c.finish(result(c.begin(request(c)), data))


@pytest.mark.parametrize(
    "condition", ["valid", "not_consumed", "different_failure", "no_explicit_successor", "wrong_successor"]
)
def test_only_explicit_owner_preparation_can_supersede_reviewed_failure(repo, condition):
    prior = "owner-x1-identity-1755-20260911-01"
    successor = "owner-x1-identity-1755-20260911-02"
    prepare(repo, prior, "2026-09-11", PICKUPS, DELIVERIES)
    if condition != "not_consumed":
        c = ReadController(repo)
        c.finish(result(c.begin(request(c)), session()))
        c.begin(request(c))
        c.fail(
            PermissionError("ACTIVE_VIEW_UNVERIFIED" if condition != "different_failure" else "BOARD_CHANGED")
        )
    with repo.database() as db:
        before = db.execute(
            "SELECT body FROM x1_read_events WHERE attempt_id=? ORDER BY rowid", (prior,)
        ).fetchall()
    kwargs = {"supersedes_attempt": prior} if condition != "no_explicit_successor" else {}
    target = successor if condition != "wrong_successor" else successor + "-unreviewed"
    if condition == "valid":
        new = prepare(repo, target, "2026-09-11", PICKUPS, DELIVERIES, **kwargs)
        assert new["supersedes_attempt"] == prior
        assert ReadController(repo).plan()["attempt_id"] == successor
        with pytest.raises(PermissionError):
            prepare(repo, target, "2026-09-11", PICKUPS, DELIVERIES, **kwargs)
        with repo.database() as db:
            assert db.execute("SELECT 1 FROM consumed WHERE kind='x1-read' AND id=?", (prior,)).fetchone()
            assert not db.execute(
                "SELECT 1 FROM consumed WHERE kind='x1-read' AND id=?", (successor,)
            ).fetchone()
    else:
        with pytest.raises(PermissionError):
            prepare(repo, target, "2026-09-11", PICKUPS, DELIVERIES, **kwargs)
    with repo.database() as db:
        assert (
            db.execute(
                "SELECT body FROM x1_read_events WHERE attempt_id=? ORDER BY rowid", (prior,)
            ).fetchall()
            == before
        )
