"""AUTO_MAP uses reviewed provider navigation fixtures only; no live execution."""
import asyncio
import json
import os

import pytest
from pydantic import ValidationError

from executors.ascend_extension.auto_map import approve_navigation
from executors.ascend_extension.mapping_store import record_mapping_validation, report_maps
from executors.ascend_extension.workspace_contracts import AutoMapNavigationCommand, MappingSessionApproval, VerifiedSectionNavigation, fingerprint
from tests.test_ascend_x1_controller import repo as repo, session
from tests.test_ascend_x1_runtime import runtime as runtime, wake, result
from tests.test_x1_workspace_mapping import IDS, approval, provider_map, capture
from tests.test_ascend_x1_dom import EXT


def mapped(number="1755", section="Load Basics", at=1000.0):
    m = provider_map(number, section, at)
    candidates = []
    for index, name in enumerate(["Load Basics", "Customer Info"]):
        c = dict(section=name, tag="button", role="tab", control_type="button", reference="ARIA_CONTROLS", relative_path=[1, index], target_relative_path=[2 + index], same_document_target=True)
        candidates.append({**c, "fingerprint": fingerprint(c)})
    m["workspace"]["navigation_candidates"] = candidates
    return m


def seed_navigation(access, controller):
    access.enable(mapping=approval(), owner_authorized=True)
    capture(controller, access, mapped())
    capture(controller, access, mapped(section="Customer Info"))
    capture(controller, access, mapped())
    approve_navigation(access, approval().session_id, ["Load Basics", "Customer Info"], owner_authorized=True)


def auto_approval(normal=False):
    return MappingSessionApproval(session_id="owner-x1-mapping-auto-normal-fixture" if normal else "owner-x1-mapping-auto-cohort-fixture",
        mode="NORMAL_OWNER_PRESENT" if normal else "FIRST_VALIDATION", operation_mode="AUTO_MAP", approved_load_ids=None if normal else IDS)


def initial(controller, access, number="1755", request=True):
    if request:
        access.request_mapping_capture(owner_authorized=True)
    d = wake(controller)
    controller.finish(result(d, session()))
    d = wake(controller)
    assert d["command"]["operation"] == "ASCEND_MAP_WORKSPACE"
    return controller.finish(result(d, mapped(number)))


def finish_cycle(controller, number="1755"):
    for target in ["Customer Info", "Load Basics"]:
        d = wake(controller)
        command = AutoMapNavigationCommand.model_validate(d["command"])
        assert command.operation == "ASCEND_MAP_NAVIGATE_SECTION" and command.load_id == number
        assert command.navigation.candidate.section == target
        final = controller.finish(result(d, mapped(number, target)))
    return final


def test_auto_requires_reviewed_navigation_and_observe_cannot_traverse(runtime):
    access, controller, *_ = runtime
    access.enable(mapping=auto_approval(), owner_authorized=True)
    stopped = initial(controller, access)
    assert stopped["status"]["state"] == "STOPPED"
    assert stopped["status"]["error_code"] == "NAVIGATION_CONTRACT_UNVERIFIED"
    assert "command" not in wake(controller)
    with pytest.raises(PermissionError):
        approve_navigation(access, "unknown", ["Save"], owner_authorized=True)


def test_auto_cohort_generalizes_returns_start_then_no_permanent_id_list(runtime):
    access, controller, now, *_ = runtime
    seed_navigation(access, controller)
    with pytest.raises(PermissionError, match="MAPPING_VALIDATION_REQUIRED"):
        access.enable(mapping=auto_approval(normal=True), owner_authorized=True)
    access.enable(mapping=auto_approval(), owner_authorized=True)
    for number in IDS:
        started = initial(controller, access, number)
        assert started["status"]["auto_map_active"]
        finished = finish_cycle(controller, number)
        assert not finished["status"]["auto_map_active"]
        assert finished["status"]["auto_last_cycle"]["returned_to_start"]
    qualification = record_mapping_validation(access, auto_approval().session_id, owner_authorized=True)
    assert qualification["operation_mode"] == "AUTO_MAP"
    access.enable(mapping=auto_approval(normal=True), owner_authorized=True)
    initial(controller, access, "999777", request=False)
    finished = finish_cycle(controller, "999777")
    assert finished["status"]["auto_last_cycle"]["load_id"] == "999777"
    assert report_maps(access, auto_approval(normal=True).session_id)["captures"] == 3
    with access.database(readonly=True) as db:
        receipts = [json.loads(r[0]) for r in db.execute("SELECT body FROM runtime_receipts")]
    navigation = [r for r in receipts if r["operation"] == "ASCEND_MAP_NAVIGATE_SECTION"]
    assert all(r["navigation_contract"]["classification"] == "READ_ONLY_NAVIGATION" for r in navigation)
    now[0] += 61
    d = wake(controller)
    controller.finish(result(d, session()))
    d = wake(controller)
    unchanged = controller.finish(result(d, mapped("999777", at=now[0])))
    assert unchanged["status"]["mapping_noop"] and not unchanged["status"]["auto_map_active"]
    assert len(report_maps(access, auto_approval(normal=True).session_id)["auto_map_cycles"]) == 1


@pytest.mark.parametrize("failure", ["identity", "revoke", "navigation", "section"])
def test_auto_failures_do_not_continue_or_complete_cycle(runtime, failure):
    access, controller, *_ = runtime
    seed_navigation(access, controller)
    access.enable(mapping=auto_approval(), owner_authorized=True)
    initial(controller, access)
    d = wake(controller)
    if failure == "revoke":
        access.disable(owner_authorized=True)
        with pytest.raises(PermissionError, match="READ_LEASE_REVOKED"):
            controller.finish(result(d, mapped(section="Customer Info")))
    else:
        m = mapped(number=IDS[1] if failure == "identity" else "1755", section="Load Basics" if failure == "section" else "Customer Info")
        stopped = controller.finish(result(d, m, "NAVIGATION_CONTROL_CHANGED" if failure == "navigation" else None))
        assert stopped["status"]["state"] == "STOPPED"
    assert "command" not in wake(controller)
    with access.database(readonly=True) as db:
        assert db.execute("SELECT count(*) FROM runtime_auto_map_cycles").fetchone()[0] == 0


def test_review_cannot_authorize_arbitrary_selectors_or_write_labels(runtime):
    access, controller, *_ = runtime
    seed_navigation(access, controller)
    with access.database(readonly=True) as db:
        value = json.loads(db.execute("SELECT body FROM runtime_navigation_contracts LIMIT 1").fetchone()[0])
    with pytest.raises(ValidationError):
        VerifiedSectionNavigation.model_validate({**value, "selector": "#save"})
    with pytest.raises(ValidationError):
        VerifiedSectionNavigation.model_validate({**value, "classification": "WRITE"})
    with pytest.raises(PermissionError):
        approve_navigation(access, approval().session_id, ["Save"], owner_authorized=True)


def test_auto_dom_transitions_and_preclick_gates(tmp_path):
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel="msedge", headless=True, env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)})
            context = await browser.new_context(service_workers="block")
            await context.route("**/*", lambda r: r.fulfill(content_type="text/html", body="<title>Offline AUTO_MAP fixture</title>"))
            page = await context.new_page()
            try:
                await page.goto("https://ascendtms.com/loads")
                for file in ["contract.js", "read-errors.js", "load-board-view.js", "detail-scope.js", "webbridge.js", "mapping-scope.js", "workspace.js", "reader.js"]:
                    await page.add_script_tag(path=str(EXT / file))
                html = '''<nav><a>Dashboard</a><a>Loads</a><a>Customers</a><a>Carriers</a></nav><main><h1>Load #1755</h1>
                <div role="tablist"><button type="button" role="tab" aria-controls="basics" aria-selected="true">Load Basics</button>
                <button type="button" role="tab" aria-controls="customer" aria-selected="false">Customer Info</button></div>
                <section id="basics" role="tabpanel"><h2>Load Basics</h2><label for="f">Equipment</label><input id="f" value="PRIVATE"></section>
                <section id="customer" role="tabpanel" hidden><h2>Customer Info</h2><label for="c">Customer</label><input id="c" value="PRIVATE"></section>
                <button id="save" type="submit">Save</button></main>'''
                async def setup():
                    await page.evaluate("html=>document.body.innerHTML=html", html)
                    await page.evaluate("""()=>{window.clicks=[];window.writes=0;document.getElementById('save').onclick=()=>writes++;
                      document.querySelectorAll('[role=tab]').forEach(t=>t.onclick=()=>{clicks.push(t.textContent);document.querySelectorAll('[role=tab]').forEach(x=>x.setAttribute('aria-selected',String(x===t)));
                        document.querySelectorAll('[role=tabpanel]').forEach(x=>x.hidden=x.id!==t.getAttribute('aria-controls'));});}""")
                    observed = await page.evaluate("()=>FreightDeskWorkspace.capture(document,null,()=>{})")
                    return observed
                observed = await setup()
                def command(target, current="Load Basics"):
                    candidate = next(c for c in observed["workspace"]["navigation_candidates"] if c["section"] == target)
                    nav = dict(candidate=candidate, confidence="VERIFIED", classification="READ_ONLY_NAVIGATION", workspace_fingerprint=observed["workspace"]["shell_fingerprint"], evidence_map_version=1, review_source="OWNER_REVIEWED_PROVIDER_NAVIGATION")
                    return AutoMapNavigationCommand(request_id="a" * 32, load_id="1755", approved_load_ids=None, owner_present=True,
                        lease_expires_at=2_000_000_000.0, navigation=nav, expected_from_section=current, return_to_start=target == "Load Basics").model_dump()
                async def execute(cmd, revoke=False):
                    return await page.evaluate("""async ({cmd,revoke})=>{try{const r=await FreightDeskX1Reader.create(document,location.origin);
                      return {map:await r.executeRuntime(cmd,()=>{if(revoke)throw Error('READ_LEASE_REVOKED')})}}catch(e){return {error:e.message}}}""", {"cmd": cmd, "revoke": revoke})
                target = command("Customer Info")
                mapped_result = await execute(target)
                assert mapped_result["map"]["section"]["section"] == "Customer Info"
                assert (await execute(command("Load Basics", "Customer Info")))["map"]["section"]["section"] == "Load Basics"
                assert await page.evaluate("clicks") == ["Customer Info", "Load Basics"]
                assert await page.evaluate("writes") == 0 and "PRIVATE" not in json.dumps(mapped_result)
                for fault in ["revoke", "identity", "duplicate", "changed", "selector", "session"]:
                    await setup()
                    cmd = json.loads(json.dumps(target))
                    if fault == "identity":
                        cmd["load_id"] = "999999"
                    elif fault == "duplicate":
                        await page.evaluate("()=>{const e=document.querySelectorAll('[role=tab]')[1];e.parentElement.append(e.cloneNode(true));}")
                    elif fault == "changed":
                        await page.evaluate("()=>document.querySelectorAll('[role=tab]')[1].type='submit'")
                    elif fault == "selector":
                        cmd["navigation"]["selector"] = "#save"
                    elif fault == "session":
                        await page.evaluate("()=>document.querySelector('nav').remove()")
                    stopped = await execute(cmd, fault == "revoke")
                    assert "error" in stopped, fault
                    assert await page.evaluate("clicks.length+writes") == 0
                await setup()
                await page.evaluate("()=>document.querySelectorAll('[role=tab]')[1].addEventListener('click',()=>document.querySelector('h1').textContent='Load #999999')")
                assert (await execute(target))["error"] == "WORKSPACE_CHANGED"
                assert await page.evaluate("clicks.length") == 1 and await page.evaluate("writes") == 0
            finally:
                await context.close()
                await browser.close()
    asyncio.run(run())
