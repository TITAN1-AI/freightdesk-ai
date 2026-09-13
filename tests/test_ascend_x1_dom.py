"""Synthetic, network-fulfilled Edge fixtures; never the approved live Ascend browser profile."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from executors.ascend_extension.contracts import ReadCommand
from executors.ascend_extension.native import canonical
from integrations.ascend.ops_board import HEADERS

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extensions" / "ascend-x1"
PICKUPS = ["1755", "1756", "1757", "1758", "1759", "1762", "1768", "1769"]
DELIVERIES = ["1761", "1766", "1767"]


def markup():
    nav = (
        "<nav>"
        + "".join(
            f'<a href="#">{label}</a>'
            for label in [
                "Dashboard",
                "Loads",
                "Customers",
                "Carriers",
                "Locations",
                "Reporting",
                "Accounting",
                "Settings",
            ]
        )
        + "</nav>"
    )
    hs = "<thead><tr>" + "".join("<th>" + (h or "") + "</th>" for h in HEADERS) + "</tr></thead>"
    rows = []
    for number in sorted(PICKUPS + DELIVERIES, key=int):
        cells = ["PRIVATE_OPERATIONAL"] * 33
        cells[0] = (
            f'<a id="open-{number}" href="#detail" data-target="#detail" data-load-id="{number}">{number}</a>'
        )
        cells[5] = "09/11/2026" if number in PICKUPS else "09/10/2026"
        cells[7] = "09/11/2026" if number in DELIVERIES else "09/12/2026"
        rows.append("<tr>" + "".join("<td>" + v + "</td>" for v in cells) + "</tr>")
    return (
        nav
        + '<a role="tab" aria-selected="true">Active Loads</a><table>'
        + hs
        + "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def test_identity_only_dom_strategies_and_failure_boundaries(tmp_path):
    async def run():
        from playwright.async_api import async_playwright

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
                cases = [
                    "field",
                    "opener",
                    "selected",
                    "conflict",
                    "click_only",
                    "ambiguous",
                    "no_panel",
                    "unsafe",
                    "board_changed",
                    "row_replaced",
                    "pairing_lost",
                    "container_bound",
                    "field_bound",
                    "already_selected",
                    "delayed",
                ]
                for case in cases:
                    page = await context.new_page()
                    await page.goto("https://ascendtms.com/loads?PRIVATE_QUERY")
                    await page.set_content(markup())
                    for file in ("contract.js", "read-errors.js", "load-board-view.js", "reader.js"):
                        await page.add_script_tag(path=str(EXT / file))
                    await page.evaluate("""async () => {
                        window.reader=await FreightDeskX1Reader.create(document,location.origin);window.alive=true;
                        Object.defineProperty(document,'cookie',{get(){throw Error('PRIVATE_COOKIE_READ_FORBIDDEN');}});
                        for(const row of document.querySelectorAll('tbody tr'))for(const [i,cell] of [...row.children].entries()){
                            if(![0,5,7].includes(i))Object.defineProperty(cell,'textContent',{get(){throw Error('PRIVATE_FIELD_READ_FORBIDDEN');}});
                        }
                    }""")

                    async def execute(operation, revision=None):
                        cmd = ReadCommand(
                            request_id=uuid4().hex,
                            operation=operation,
                            load_id="1755" if revision else None,
                            expected_revision=revision,
                        )
                        return await page.evaluate(
                            """async c=>{
                            try{return {ok:true,evidence:await reader.executeIdentity(c,()=>{if(!alive)throw Error('PAIRING_LOST');})};}
                            catch(error){return {ok:false,error_code:FreightDeskReadErrors.safe(error)};}
                        }""",
                            cmd.model_dump(),
                        )

                    assert (await execute("ASCEND_GET_SESSION_STATE"))["evidence"][
                        "authenticated_app"
                    ] is True
                    board = (await execute("ASCEND_GET_ACTIVE_LOADS"))["evidence"]
                    assert len(board["rows"]) == 11 and board["coverage"] == "VISIBLE_BOARD_ONLY"
                    assert all(set(row) == {"load_id", "pick_date", "drop_date"} for row in board["rows"])
                    assert board["board_hash"] == hashlib.sha256(canonical(board["rows"])).hexdigest()
                    revision = board["board_hash"]
                    assert (await execute("ASCEND_FIND_LOAD", revision))["evidence"]["exact_row"] is True
                    await page.evaluate(
                        """kind=>{
                        const open=document.getElementById('open-1755');
                        if(['field','selected','click_only','delayed','already_selected'].includes(kind))open.removeAttribute('data-load-id');
                        if(kind==='click_only'){open.setAttribute('href','#');open.removeAttribute('data-target');}
                        if(kind==='already_selected')open.setAttribute('aria-expanded','true');
                        if(kind==='unsafe')open.setAttribute('href','/loads/1755');
                        if(kind==='row_replaced'){const row=open.closest('tr');row.replaceWith(row.cloneNode(true));return;}
                        open.addEventListener('click',event=>{
                            event.preventDefault();
                            window.clicks=(window.clicks||0)+1;
                            if(kind==='pairing_lost'){window.alive=false;return;}
                            if(kind==='no_panel')return;
                            if(kind==='selected')open.setAttribute('aria-expanded','true');
                            const render=()=>{
                                const panel=document.createElement('div');panel.setAttribute('role','dialog');panel.id='detail';
                                if(['field','conflict','delayed'].includes(kind)){
                                    panel.innerHTML='<label for=load-id>Load ID</label><input id=load-id value='+ (kind==='conflict'?'1756':'1755') +'>';
                                }
                                panel.innerHTML+='<textarea id=private-note>PRIVATE_NOTES</textarea><input name=driver_phone id=private-phone value=PRIVATE_PHONE>';
                                document.body.append(panel);
                                for(const el of panel.querySelectorAll('#private-note,#private-phone'))Object.defineProperty(el,'value',{get(){throw Error('PRIVATE_READ_FORBIDDEN');}});
                                if(kind==='ambiguous')document.body.append(panel.cloneNode(true));
                                if(kind==='container_bound')for(let i=0;i<12;i++)document.body.append(panel.cloneNode(true));
                                if(kind==='field_bound')for(let i=0;i<65;i++)panel.append(document.createElement('label'));
                                if(kind==='board_changed')open.closest('tr').children[5].textContent='09/12/2026';
                            };
                            if(kind==='delayed')setTimeout(render,250);else render();
                        });
                    }""",
                        case,
                    )
                    result = await execute("ASCEND_OPEN_LOAD_READONLY", revision)
                    if case in ("field", "opener", "selected", "delayed"):
                        assert result["ok"], (case, result)
                        evidence = result["evidence"]
                        assert evidence["observed_load_id"] == "1755"
                        assert (
                            evidence["identity_strategy"]
                            == {
                                "field": "PROVIDER_DETAIL_FIELD",
                                "delayed": "PROVIDER_DETAIL_FIELD",
                                "opener": "PROVIDER_OPENER_IDENTITY",
                                "selected": "PROVIDER_SELECTED_ROW_BINDING",
                            }[case]
                        )
                        assert not any(
                            k in json.dumps(evidence)
                            for k in ("PRIVATE", "stop_section", "appointment", "driver", "carrier", "notes")
                        )
                    else:
                        assert not result["ok"], case
                        assert (
                            result["error_code"]
                            == {
                                "conflict": "DETAIL_IDENTITY_CONFLICT",
                                "click_only": "DETAIL_IDENTITY_MISSING",
                                "ambiguous": "DETAIL_IDENTITY_AMBIGUOUS",
                                "no_panel": "DETAIL_IDENTITY_MISSING",
                                "unsafe": "UNSAFE_OPENER",
                                "board_changed": "BOARD_CHANGED",
                                "row_replaced": "TAB_STATE_CHANGED",
                                "pairing_lost": "PAIRING_LOST",
                                "container_bound": "IDENTITY_BOUND_EXCEEDED",
                                "field_bound": "IDENTITY_BOUND_EXCEEDED",
                                "already_selected": "DETAIL_IDENTITY_MISSING",
                            }[case]
                        ), (case, result)
                    assert (await page.evaluate("window.clicks||0")) == (
                        0 if case in ("unsafe", "row_replaced") else 1
                    )
                    # Even after identity succeeds, this production entrypoint cannot read operational fields.
                    assert (await execute("ASCEND_READ_LOAD", revision))["error_code"] == (
                        "PAIRING_LOST" if case == "pairing_lost" else "COMMAND_NOT_ALLOWED"
                    )
                    await page.close()
                for path, body, expected in [
                    ("/login.html", "<input type=password>", False),
                    ("/", markup(), True),
                    ("/loads", "<p>No app</p>", False),
                ]:
                    page = await context.new_page()
                    await page.goto("https://ascendtms.com" + path)
                    await page.set_content(body)
                    for file in ("contract.js", "load-board-view.js", "reader.js"):
                        await page.add_script_tag(path=str(EXT / file))
                    cmd = ReadCommand(request_id=uuid4().hex, operation="ASCEND_GET_SESSION_STATE")
                    result = await page.evaluate(
                        "async c=>(await FreightDeskX1Reader.create(document,location.origin)).executeIdentity(c,()=>{})",
                        cmd.model_dump(),
                    )
                    assert result["authenticated_app"] is expected
                    await page.close()
            finally:
                await context.close()

    asyncio.run(run())
