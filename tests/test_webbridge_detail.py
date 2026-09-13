"""Isolated fulfilled DOM fixtures only; no installed profile, native host or vendor networking."""

import asyncio
import json
import os
from uuid import uuid4

from executors.ascend_extension.detail_contract import AscendLoadDetailContract, SCOPE
from tests.test_ascend_x1_controller import view_contract
from tests.test_ascend_x1_dom import EXT, markup


def identity(number="1755", revision="a" * 64):
    return dict(expected_load_id=number, observed_load_id=number, identity_strategy="PROVIDER_DETAIL_FIELD",
                confidence="VERIFIED", board_hash=revision, row_match=True, opener_belongs_to_row=True,
                unique_panel=True, detail_field_match=True, direct_panel_reference=True,
                opener_identity_match=True, selection_transition=False, newly_visible=True,
                view_contract=view_contract())


def test_webbridge_sensor_differential_and_runtime_integration(tmp_path):
    async def run():
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                str(tmp_path / "fixture"), channel="msedge", headless=True, service_workers="block",
                env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
            )
            requests = []

            async def intercept(route):
                requests.append(route.request.url)
                assert route.request.url == "https://ascendtms.com/loads"
                await route.fulfill(content_type="text/html", body="<title>Offline fixture</title>")

            await context.route("**/*", intercept)
            page = await context.new_page()
            await page.goto("https://ascendtms.com/loads")
            for file in ["contract.js", "read-errors.js", "load-board-view.js", "detail-scope.js", "webbridge.js", "reader.js"]:
                await page.add_script_tag(path=str(EXT / file))
            console = []
            page.on("console", lambda msg: console.append(msg.text))

            async def observe(html, proof=None):
                await page.evaluate("html=>document.body.innerHTML=html", '<div role="dialog" id="detail">' + html + '</div>')
                return await page.evaluate("async i=>FreightDeskWebBridge.BrowserSensor.discover(document.getElementById('detail'),i,['DIRECT_REFERENCE'])", proof or identity())

            def field(contract, key):
                return next(f for f in contract["fields"] if f["field"] == key)

            labeled = '<section><h2>Assignment</h2><label for="carrier">Carrier</label><input id="carrier" value="PRIVATE_CARRIER"></section>'
            exact = await observe(labeled)
            AscendLoadDetailContract.model_validate(exact)
            assert field(exact, "carrier")["confidence"] == "VERIFIED"
            assert field(exact, "carrier")["evidence_level"] == "LEVEL_2"
            assert set(f["field"] for f in exact["fields"]) == set(SCOPE)
            assert "PRIVATE" not in json.dumps(exact)
            assert exact["activation"] == "CANDIDATE_ONLY" and not exact["writes_allowed"]

            # A changed selector/location cannot silently activate a mapping; strong semantics can propose remap.
            changed = await observe(labeled.replace('id="carrier"', 'id="carrier-v2"').replace('for="carrier"', 'for="carrier-v2"').replace('<input', '<span></span><input'))
            assert changed["contract_fingerprint"] != exact["contract_fingerprint"]
            remap = await page.evaluate("([a,b])=>FreightDeskWebBridge.AdaptiveLocator.propose(a,b)", [field(exact, "carrier"), field(changed, "carrier")])
            assert remap["result"] == "PROPOSED_READ_REMAP" and remap["activation"] == "CANDIDATE_ONLY"
            # Values/presence do not change structural fingerprint.
            empty = await observe(labeled.replace("PRIVATE_CARRIER", ""))
            assert field(empty, "carrier")["presence"] == "EMPTY"
            assert empty["contract_fingerprint"] == exact["contract_fingerprint"]

            cases = [
                (labeled.replace('</section>', '<label for="other">Carrier</label><input id="other" value="CONFLICT"></section>'), "UNKNOWN", None),
                (labeled.replace('<input', '<input hidden'), "UNKNOWN", None),
                (labeled.replace('<input', '<input aria-hidden="true"'), "UNKNOWN", None),
                (labeled.replace('Assignment', 'Pickup'), "UNKNOWN", None),
                ('<section><h2>Assignment</h2><span>Carrier</span><input value="PRIVATE"></section>', "PROPOSED", "LEVEL_3"),
                ('<section><h2>Assignment</h2><input data-field="carrier" value="PRIVATE"></section>', "VERIFIED", "LEVEL_1"),
                (labeled.replace('<input', '<input aria-label="Driver Name"'), "UNKNOWN", None),
                (labeled.replace('<input', '<input aria-label="Income"'), "UNKNOWN", None),
                ('<section><h2>Assignment</h2><input aria-label="Carrier" value="PRIVATE"></section>', "VERIFIED", "LEVEL_2"),
                ('<section><h2>Assignment</h2><span id="label">Carrier</span><input aria-labelledby="label" value="PRIVATE"></section>', "VERIFIED", "LEVEL_2"),
                ('<section><h2>Assignment</h2><table><thead><tr><th>Carrier</th></tr></thead><tbody><tr><td><input value="PRIVATE"></td></tr></tbody></table></section>', "PROPOSED", "LEVEL_3"),
            ]
            for html, confidence, level in cases:
                observed = await observe(html)
                AscendLoadDetailContract.model_validate(observed)
                assert field(observed, "carrier")["confidence"] == confidence
                assert field(observed, "carrier")["evidence_level"] == level
                assert "PRIVATE" not in json.dumps(observed)

            # Same Address label in two explicit stop sections stays separated; no timezone/date inference.
            stops = await observe('<section><h2>Pickup</h2><label>Address<input value="PRIVATE_ADDRESS"></label></section><section><h2>Delivery</h2><label>Address<input value="PRIVATE_ADDRESS2"></label></section>')
            assert field(stops, "pickup_address")["confidence"] == "VERIFIED"
            assert field(stops, "delivery_address")["confidence"] == "VERIFIED"

            # Identity gate executes before touching any operational value; excluded fields are never sampled.
            await observe(labeled + '<section><h2>Assignment</h2><label>Private Notes<textarea id="notes">PRIVATE</textarea></label><label>Income<input id="income" value="PRIVATE"></label></section>')
            await page.evaluate("()=>{for(const id of ['notes','income'])Object.defineProperty(document.getElementById(id),'value',{get(){throw Error('PRIVATE_VALUE_READ');}});}")
            safe = await page.evaluate("i=>FreightDeskWebBridge.BrowserSensor.discover(document.getElementById('detail'),i,['NEW_CONTAINER'])", identity())
            assert "PRIVATE" not in json.dumps(safe)
            await page.evaluate("()=>Object.defineProperty(document.getElementById('carrier'),'value',{get(){throw Error('MUST_NOT_READ');}})")
            for bad in [dict(identity(), observed_load_id="999"), dict(identity(), confidence="UNKNOWN"), dict(identity(), detail_field_match=False)]:
                result = await page.evaluate("async i=>{try{await FreightDeskWebBridge.BrowserSensor.discover(document.getElementById('detail'),i,['NEW_CONTAINER']);return 'BAD';}catch(e){return e.message;}}", bad)
                assert result == "DETAIL_IDENTITY_MISSING"

            # Causal differential: new/newly visible roots; unrelated structure is ignored.
            for before, after, reason in [
                ('', '<div role="dialog"><h2>Assignment</h2></div>', 'NEW_CONTAINER'),
                ('<div role="dialog" hidden></div>', None, 'NEWLY_VISIBLE'),
            ]:
                await page.evaluate("html=>{document.body.innerHTML=html;window.before=FreightDeskWebBridge.DOMSnapshot.capture(document);}", before)
                if after:
                    await page.evaluate("html=>document.body.insertAdjacentHTML('beforeend',html)", after)
                elif reason == 'NEWLY_VISIBLE':
                    await page.evaluate("()=>document.querySelector('[role=dialog]').hidden=false")
                else:
                    await page.evaluate("()=>{const p=document.querySelector('[role=dialog]');p.setAttribute('aria-selected','true');p.querySelector('h2').textContent='Pickup';}")
                reasons = await page.evaluate("()=>FreightDeskWebBridge.DOMDiff.compare(window.before,document).map(c=>c.reasons)")
                assert reason in reasons[0]
            await page.evaluate("()=>{document.body.innerHTML='<div role=dialog></div>';window.before=FreightDeskWebBridge.DOMSnapshot.capture(document);document.body.insertAdjacentHTML('beforeend','<div>'+('<span>PRIVATE</span>'.repeat(2000))+'</div>');}")
            assert await page.evaluate("()=>FreightDeskWebBridge.DOMDiff.compare(window.before,document).length") == 0
            await page.evaluate("()=>{document.body.innerHTML='<div role=dialog></div>'.repeat(40);window.before=FreightDeskWebBridge.DOMSnapshot.capture(document);}")
            assert await page.evaluate("()=>FreightDeskWebBridge.DOMDiff.compare(window.before,document).length") == 0

            # End-to-end existing fixed FIND -> OPEN -> identity -> discovery, not arbitrary sensor access.
            await page.evaluate("html=>document.body.innerHTML=html", markup())
            await page.evaluate("()=>{window.reader=FreightDeskX1Reader.create(document,location.origin);document.getElementById('open-1755').onclick=e=>{e.preventDefault();document.body.insertAdjacentHTML('beforeend','<div id=detail role=dialog><h2>Load # 1755</h2><section><h2>Assignment</h2><label>Carrier<input value=PRIVATE></label></section></div>');};}")

            async def execute(op, revision=None):
                command = dict(version=1, request_id=uuid4().hex, operation=op, load_id="1755" if revision else None,
                               expected_revision=revision, tenant_id="booking-logistics", actor="FreightDesk/Avery")
                return await page.evaluate("async c=>(await window.reader).executeRuntime(c,()=>{})", command)

            board = await execute("ASCEND_GET_ACTIVE_LOADS")
            revision = board["board_hash"]
            await execute("ASCEND_FIND_LOAD", revision)
            await execute("ASCEND_OPEN_LOAD_READONLY", revision)
            observed = await execute("ASCEND_DISCOVER_DETAIL_CONTRACT", revision)
            AscendLoadDetailContract.model_validate(observed["contract"])
            assert field(observed["contract"], "carrier")["confidence"] == "VERIFIED"
            assert "PRIVATE" not in json.dumps(observed)
            assert not console
            assert requests == ["https://ascendtms.com/loads"]  # fulfilled locally, no other provider/network requests
            await context.close()

    asyncio.run(run())
