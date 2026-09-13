"""Causal DOM fixtures only. All browser requests fulfilled locally; never the live profile."""

import asyncio
import json
import os
from uuid import uuid4

from executors.ascend_extension.detail_contract import AscendLoadDetailContract
from executors.ascend_extension.detail_diagnostics import DetailContainerDiagnostic
from tests.test_ascend_x1_dom import EXT, markup


def test_causal_container_relationships_bounds_and_identity(tmp_path):
    async def run():
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                str(tmp_path / "causal-fixture-profile"), channel="msedge", headless=True,
                service_workers="block", env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
            )
            requests = []

            async def fulfill(route):
                requests.append(route.request.url)
                await route.fulfill(content_type="text/html", body="<title>Offline container fixture</title>")

            await context.route("**/*", fulfill)
            try:
                page = await context.new_page()
                await page.goto("https://ascendtms.com/loads")
                for file in ("contract.js", "read-errors.js", "load-board-view.js", "detail-scope.js", "webbridge.js", "reader.js"):
                    await page.add_script_tag(path=str(EXT / file))

                async def causal(before="", after="", setup=""):
                    value = await page.evaluate("""({before,after,setup})=>{
                        document.body.innerHTML='<div id=row><a id=open>1755</a></div>'+before;
                        const row=document.getElementById('row'),opener=document.getElementById('open');
                        new Function(setup)();
                        try{
                            const snap=FreightDeskWebBridge.DOMSnapshot.capture(document,{row,opener,loadId:'1755'});
                            FreightDeskWebBridge.DOMSnapshot.markClicked(snap);new Function(after)();
                            const candidates=FreightDeskWebBridge.DOMDiff.compare(snap,document);
                            const choice=candidates.length?FreightDeskWebBridge.AdaptiveLocator.selectContainer(candidates):null;
                            return {ok:true,level:choice?.level||null,diagnostic:FreightDeskWebBridge.diagnostic()};
                        }catch(e){return {ok:false,code:FreightDeskReadErrors.safe(e),diagnostic:FreightDeskWebBridge.diagnostic()};}
                    }""", dict(before=before, after=after, setup=setup))
                    assert "PRIVATE" not in json.dumps(value)
                    DetailContainerDiagnostic.model_validate(value["diagnostic"])
                    return value

                chrome = '<nav>' + '<div role=tabpanel>PRIVATE</div>' * 150 + '</nav>'
                unchanged = '<div class=side-panel><h2>PRIVATE</h2><form><input value=PRIVATE></form></div>' * 60
                result = await causal(chrome + unchanged)
                assert result["ok"] and result["diagnostic"]["candidate_count"] == 0
                assert result["diagnostic"]["ignored_unchanged_count"] == 120
                result = await causal(chrome + unchanged,
                    "document.body.insertAdjacentHTML('beforeend','<div role=dialog><form></form><div role=tabpanel></div></div>');")
                assert result["ok"] and result["level"] == "B" and result["diagnostic"]["candidate_count"] == 1
                result = await causal('<div id=detail class=side-panel hidden></div>', "document.getElementById('detail').hidden=false;")
                assert result["level"] == "C"
                result = await causal('<div id=detail><h2>Load # 1755</h2></div>', setup="document.getElementById('open').setAttribute('href','#detail');")
                assert result["level"] == "A"  # Direct provider target may be a plain div, never body/nav.
                result = await causal('', "document.body.insertAdjacentHTML('beforeend','<div id=detail role=dialog></div><div role=dialog></div><form></form>');",
                    "document.getElementById('open').setAttribute('data-target','#detail');")
                assert result["level"] == "A" and result["diagnostic"]["candidate_count"] == 3
                assert result["diagnostic"]["ranked_candidates"][0]["reasons"] == ["DIRECT_REFERENCE", "NEW_CONTAINER"]
                result = await causal('', "document.body.insertAdjacentHTML('beforeend','<div role=dialog></div>'.repeat(2));")
                assert result["code"] == "DETAIL_IDENTITY_AMBIGUOUS"
                result = await causal('', "document.body.insertAdjacentHTML('beforeend','<div id=detail role=dialog></div>'.repeat(2));",
                    "document.getElementById('open').setAttribute('href','#detail');")
                assert result["code"] == "DETAIL_IDENTITY_AMBIGUOUS"  # Duplicate provider target IDs are not a unique binding.
                result = await causal('<div id=detail role=tabpanel aria-labelledby=open></div>',
                    "document.getElementById('detail').setAttribute('aria-selected','true');")
                assert result["level"] == "D"
                result = await causal('<div id=detail role=tabpanel></div>',
                    "document.getElementById('detail').setAttribute('aria-selected','true');")
                assert result["diagnostic"]["candidate_count"] == 0  # Unconnected selection changes cannot authorize a read.

                for before, after, setup, category, measured, maximum in [
                    ('', '', "document.getElementById('open').setAttribute('aria-controls','a b c d e');", 'direct_targets', 5, 4),
                    ('', "document.body.insertAdjacentHTML('beforeend','<div role=dialog></div>'.repeat(9));", '', 'new_containers', 9, 8),
                    ('<div role=dialog hidden></div>' * 9, "document.querySelectorAll('[hidden]').forEach(e=>e.hidden=false);", '', 'newly_visible', 9, 8),
                    ('<div role=tabpanel aria-labelledby=open></div>' * 5, "document.querySelectorAll('[role=tabpanel]').forEach(e=>e.setAttribute('aria-selected','true'));", '', 'changed_selected', 5, 4),
                ]:
                    result = await causal(before, after, setup)
                    assert result["code"] == 'DETAIL_BOUND_' + category.upper()
                    d = result["diagnostic"]
                    assert (d["failed_category"], d["measured"], d["maximum"]) == (category, measured, maximum)
                    assert d["click_dispatched"] == (category != 'direct_targets')

                # The real reader still performs one exact fixed OPEN and verifies provider identity
                # before any field presence sampling. Many old dialogs/forms cannot consume the bound.
                await page.evaluate("html=>document.body.innerHTML=html", markup() + unchanged + chrome)
                await page.evaluate("""async()=>{
                    window.reader=await FreightDeskX1Reader.create(document,location.origin);window.clicks=0;
                    document.getElementById('open-1755').onclick=e=>{
                        e.preventDefault();window.clicks++;
                        document.body.insertAdjacentHTML('beforeend','<div id=detail role=dialog><h2>Load # 1755</h2><section><h2>Assignment</h2><label>Carrier<input id=carrier value=PRIVATE></label></section></div><div role=dialog>PRIVATE</div>');
                        Object.defineProperty(document.getElementById('carrier'),'value',{configurable:true,get(){throw Error('FIELD_READ_BEFORE_IDENTITY');}});
                    };
                }""")

                async def execute(operation, revision=None):
                    command = dict(version=1, request_id=uuid4().hex, operation=operation, load_id="1755" if revision else None,
                                   expected_revision=revision, tenant_id="booking-logistics", actor="FreightDesk/Avery")
                    return await page.evaluate("async c=>reader.executeRuntime(c,()=>{})", command)

                b = await execute("ASCEND_GET_ACTIVE_LOADS")
                revision = b["board_hash"]
                await execute("ASCEND_FIND_LOAD", revision)
                identity = await execute("ASCEND_OPEN_LOAD_READONLY", revision)
                assert identity["observed_load_id"] == "1755" and identity["container_diagnostic"]["selected_level"] == "A"
                assert await page.evaluate("window.clicks") == 1
                await page.evaluate("()=>Object.defineProperty(document.getElementById('carrier'),'value',{value:'PRIVATE'})")
                observed = await execute("ASCEND_DISCOVER_DETAIL_CONTRACT", revision)
                AscendLoadDetailContract.model_validate(observed["contract"])
                assert "PRIVATE" not in json.dumps(observed)
                assert observed["contract"]["activation"] == "CANDIDATE_ONLY"
                assert observed["contract"]["writes_allowed"] is False

                # Identity candidate overflow is measured only inside the chosen root.
                await page.evaluate("""html=>{document.body.innerHTML=html;window.reader=FreightDeskX1Reader.create(document,location.origin);
                    document.getElementById('open-1755').onclick=e=>{e.preventDefault();document.body.insertAdjacentHTML('beforeend','<div id=detail role=dialog>'+('<input name=load_id value=1755>'.repeat(65))+'</div>');};}
                """, markup())
                await page.evaluate("async()=>{window.reader=await window.reader;}")
                revision = (await execute("ASCEND_GET_ACTIVE_LOADS"))["board_hash"]
                await execute("ASCEND_FIND_LOAD", revision)
                command = dict(version=1, request_id=uuid4().hex, operation="ASCEND_OPEN_LOAD_READONLY", load_id="1755",
                               expected_revision=revision, tenant_id="booking-logistics", actor="FreightDesk/Avery")
                failure = await page.evaluate("""async c=>{try{await reader.executeRuntime(c,()=>{});return null;}catch(e){return {code:FreightDeskReadErrors.safe(e),diagnostic:reader.detailDiagnostic()};}}""", command)
                assert failure["code"] == "DETAIL_BOUND_IDENTITY_CANDIDATES"
                assert failure["diagnostic"]["measured"] == 66 and failure["diagnostic"]["maximum"] == 64
                DetailContainerDiagnostic.model_validate(failure["diagnostic"])
                assert requests == ["https://ascendtms.com/loads"]
            finally:
                await context.close()

    asyncio.run(run())
