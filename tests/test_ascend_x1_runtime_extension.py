"""Persistent extension checks use fake hosts and fulfilled, isolated browser pages only."""

import asyncio
import os
import subprocess
from uuid import uuid4

from executors.ascend_extension.runtime_contracts import RuntimeBoardEvidence, UnknownDetailEvidence
from executors.ascend_extension.view_contract import AscendLoadBoardViewContract
from tests.test_ascend_x1_dom import EXT, ROOT, markup


def test_persistent_extension_restart_and_routing_fixtures():
    result = subprocess.run(
        ["node", str(ROOT / "scripts" / "check-ascend-x1-runtime.js")],
        cwd=ROOT, capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_runtime_navigation_and_unknown_field_contracts(tmp_path):
    async def run():
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                str(tmp_path / "fixture-profile"), channel="msedge", headless=True,
                service_workers="block", env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
            )
            await context.route("**/*", lambda r: r.fulfill(content_type="text/html", body="<title>Offline fixture</title>"))
            try:
                async def page_for(body, path="/loads"):
                    page = await context.new_page()
                    await page.goto("https://ascendtms.com" + path)
                    await page.set_content(body)
                    for file in ("contract.js", "read-errors.js", "load-board-view.js", "reader.js"):
                        await page.add_script_tag(path=str(EXT / file))
                    await page.evaluate("async()=>{window.reader=await FreightDeskX1Reader.create(document,location.origin);window.clicks=0;}")
                    return page

                async def execute(page, operation, revision=None):
                    command = dict(version=1, request_id=uuid4().hex, operation=operation,
                                   load_id="1755" if revision else None, expected_revision=revision,
                                   tenant_id="booking-logistics", actor="FreightDesk/Avery")
                    return await page.evaluate("""async command=>{
                        try{return {ok:true,evidence:await reader.executeRuntime(command,()=>{})};}
                        catch(error){return {ok:false,error_code:FreightDeskReadErrors.safe(error)};}
                    }""", command)

                body = markup().replace('<a role="tab" aria-selected="true">Active Loads</a>',
                    '<div role="tablist"><button type="button" role="tab" aria-selected="true">All Loads</button>'
                    '<button type="button" role="tab" aria-selected="false">Active Loads</button></div>')
                page = await page_for(body)
                await page.evaluate("""()=>{
                    const tabs=[...document.querySelectorAll('[role=tab]')];
                    tabs[1].onclick=()=>{window.clicks++;tabs[0].setAttribute('aria-selected','false');tabs[1].setAttribute('aria-selected','true');};
                    for(const row of document.querySelectorAll('tbody tr'))for(const [i,cell] of [...row.children].entries()){
                        if(![0,5,7].includes(i))Object.defineProperty(cell,'textContent',{get(){throw Error('PRIVATE_FIELD_READ_FORBIDDEN');}});
                    }
                }""")
                result = await execute(page, "ASCEND_NAVIGATE_ACTIVE_LOADS")
                assert result["ok"]
                assert AscendLoadBoardViewContract.model_validate(result["evidence"]["view_contract"]).view == "ACTIVE_LOADS"
                assert await page.evaluate("window.clicks") == 1
                assert (await execute(page, "ASCEND_NAVIGATE_ACTIVE_LOADS"))["ok"]
                assert await page.evaluate("window.clicks") == 1
                board = (await execute(page, "ASCEND_GET_ACTIVE_LOADS"))["evidence"]
                RuntimeBoardEvidence.model_validate(board)
                revision = board["board_hash"]
                assert (await execute(page, "ASCEND_READ_LOAD", revision))["error_code"] == "DETAIL_IDENTITY_MISSING"
                assert (await execute(page, "ASCEND_FIND_LOAD", revision))["ok"]
                await page.evaluate("""()=>{
                    document.getElementById('open-1755').onclick=event=>{
                        event.preventDefault();const panel=document.createElement('div');panel.id='detail';panel.setAttribute('role','dialog');
                        panel.innerHTML='<h2>Load # 1755</h2><textarea>PRIVATE_NOTE</textarea><input name=driver_phone value=PRIVATE_PHONE>';
                        document.body.append(panel);
                    };
                }""")
                assert (await execute(page, "ASCEND_OPEN_LOAD_READONLY", revision))["ok"]
                for operation in ("ASCEND_READ_LOAD", "ASCEND_READ_STOPS", "ASCEND_READ_ASSIGNMENT"):
                    result = await execute(page, operation, revision)
                    assert result["ok"]
                    value = UnknownDetailEvidence.model_validate(result["evidence"])
                    assert value.mapping_state == "UNKNOWN" and value.fields == []
                    assert "PRIVATE" not in str(result)
                await page.close()

                # A known provider navigation anchor can move from an otherwise sanitized OTHER path.
                page = await page_for(markup().replace('<a href="#">Loads</a>', '<a href="/loads">Loads</a>'), "/private-view")
                assert (await execute(page, "ASCEND_GET_SESSION_STATE"))["evidence"]["authenticated_app"]
                await page.evaluate("""()=>{document.querySelector('nav a[href="/loads"]').onclick=event=>{
                    event.preventDefault();window.clicks++;history.pushState(null,'','/loads');};}""")
                assert (await execute(page, "ASCEND_NAVIGATE_ACTIVE_LOADS"))["error_code"] == "NAVIGATION_STARTED"
                assert (await execute(page, "ASCEND_GET_SESSION_STATE"))["evidence"]["authenticated_app"]
                assert (await execute(page, "ASCEND_NAVIGATE_ACTIVE_LOADS"))["ok"]
                assert await page.evaluate("window.clicks") == 1
                await page.close()

                # A route alone, submit control, or unsafe destination cannot initiate read navigation.
                for replacement in (
                    '<button role="tab" type="submit">Active Loads</button>',
                    '<a role="tab" href="/loads?save=1">Active Loads</a>',
                    '<button type="button" role="tab">Active Loads</button><button type="button" role="tab">Active Loads</button>',
                ):
                    page = await page_for(markup().replace('<a role="tab" aria-selected="true">Active Loads</a>', replacement))
                    await page.evaluate("()=>document.addEventListener('click',()=>window.clicks++)")
                    result = await execute(page, "ASCEND_NAVIGATE_ACTIVE_LOADS")
                    assert not result["ok"]
                    assert await page.evaluate("window.clicks") == 0
                    await page.close()
                page = await page_for(markup())
                await page.evaluate("()=>document.querySelector('tbody').innerHTML='<tr><td colspan=33 class=dataTables_empty>No data available in table</td></tr>'")
                result = await execute(page, "ASCEND_GET_ACTIVE_LOADS")
                assert result["ok"] and result["evidence"]["rows"] == []
                await page.close()
            finally:
                await context.close()

    asyncio.run(run())
