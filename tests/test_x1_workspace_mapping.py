"""Offline metadata, authorization and context fixtures; no vendor or native-host execution."""

import asyncio
import json
import os
import sqlite3
import subprocess

import pytest
from pydantic import ValidationError

from executors.ascend_extension.mapping_store import report_maps, record_mapping_validation
from executors.ascend_extension.workspace_contracts import (
    AscendProviderMap, MappingCommand, MappingSessionApproval, OPERATIONAL_VIEW_SKELETONS, SCOPE, fingerprint,
)
from integrations.ascend.context_assembler import ReadMappingValidation, VerifiedAscendLoadContextAssembler, VerifiedProviderObservation
from tests.test_ascend_x1_controller import repo as repo, route, session
from tests.test_ascend_x1_enrollment import enrollment as enrollment
from tests.test_ascend_x1_dom import EXT
from tests.test_ascend_x1_runtime import runtime as runtime, result, wake

IDS = ["1755", "900001", "900002"]  # Last two are synthetic fixtures, never owner sample recommendations.


def test_mapping_worker_orchestration_fixture():
    completed = subprocess.run(["node", "scripts/check-x1-mapping-mode.js"], capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def approval(**kwargs):
    return MappingSessionApproval(session_id="owner-x1-mapping-fixture-01", approved_load_ids=IDS, **kwargs)


def provider_map(number="1755", section="Load Basics", at=1000.0, extra=False, offset=0, level="LEVEL_2"):
    fields = []
    for i, (name, label) in enumerate([("equipment", "Equipment")] + ([("carrier", "Carrier")] if extra else [])):
        structure = dict(field_name_candidate=name, section=section, semantic_label=label, control_type="text", editable=True,
            role="OTHER", locator_graph=dict(signals=["LABEL_CONTROL"] if level == "LEVEL_2" else ["NEIGHBOR"],
            relative_path=[i + offset], neighboring_labels=[], data_attribute_names=[], aria_relationships=[]), evidence_level=level, confidence="PROPOSED")
        fields.append({**structure, "presence": "VISIBLE", "optionality": "UNKNOWN", "observed_on_load": number,
            "observed_at": at, "contract_fingerprint": fingerprint(structure)})
    workspace = dict(contract="AscendLoadWorkspaceContract", provider="AscendTMS", source="provider DOM", entity_type="LOAD", load_id=number,
        confidence="VERIFIED", signals=[dict(kind="HEADER_CONTROL", load_id=number, outside_child_section=True)],
        section_controls=["Load Basics", "Customer Info"], path_pattern="/loads", observed_at=at,
        shell_fingerprint=fingerprint(dict(signals=["HEADER_CONTROL"], sections=["Load Basics", "Customer Info"])), tenant_identity_source="OWNER_ATTESTED")
    child = dict(contract="AscendLoadSectionContract", section=section, workspace_load_id=number,
        identity_source="INHERITED_FROM_REVALIDATED_WORKSPACE", section_signal="SELECTED_CONTROL", headings=[section],
        action_controls=["Save"], fields=fields, coverage="CURRENT_VISIBLE_SECTION_ONLY",
        fingerprint=fingerprint(dict(section=section, headings=[section], actions=["Save"], fields=[f["contract_fingerprint"] for f in fields])))
    return dict(schema_version=1, provider="AscendTMS", source="live extension DOM", workspace=workspace, section=child,
        revalidated_after_capture=True, activation="CANDIDATE_ONLY", values_included=False, writes_allowed=False, owner_present=True)


def capture(controller, access, evidence=None, tab=None):
    access.request_mapping_capture(owner_authorized=True)
    dispatch = wake(controller, tab)
    assert dispatch["command"]["operation"] == "ASCEND_GET_SESSION_STATE"
    controller.finish(result(dispatch, session()))
    dispatch = wake(controller, tab)
    assert dispatch["command"]["operation"] == "ASCEND_MAP_WORKSPACE"
    return controller.finish(result(dispatch, evidence or provider_map()))


def test_mapping_owner_scope_and_no_automatic_board_reads(runtime):
    access, controller, *_ = runtime
    with pytest.raises(PermissionError, match="OWNER_REQUIRED"):
        access.enable(mapping=approval())
    access.enable(owner_authorized=True)
    with pytest.raises(PermissionError, match="MAPPING_NOT_ENABLED"):
        access.request_mapping_capture(owner_authorized=True)
    access.enable(mapping=approval(), owner_authorized=True)
    assert access.check()["allowed_operations"] == ["ASCEND_GET_SESSION_STATE", "ASCEND_MAP_WORKSPACE"]
    first = wake(controller)
    controller.finish(result(first, session()))
    for _ in range(3):
        assert wake(controller)["status"]["state"] == "MAPPING_READY"
    with pytest.raises(PermissionError, match="RUNTIME_SCOPE_INVALID"):
        access.queue_detail("1755", owner_authorized=True)
    assert capture(controller, access)["status"]["mapping_capture_count"] == 1
    with access.database(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM runtime_proposals").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM runtime_provider_maps").fetchone()[0] == 1
        operations = [json.loads(r[0])["operation"] for r in db.execute("SELECT body FROM runtime_events")]
        assert set(operations) <= {None, "ASCEND_GET_SESSION_STATE", "ASCEND_MAP_WORKSPACE"}
    with pytest.raises(PermissionError, match="MAPPING_SESSION_CONSUMED"):
        access.enable(mapping=approval(), owner_authorized=True)


def test_versions_optional_fields_navigation_and_append_only(runtime):
    access, controller, *_ = runtime
    access.enable(mapping=approval(), owner_authorized=True)
    capture(controller, access, provider_map(extra=True))
    capture(controller, access, provider_map(number=IDS[1]))
    capture(controller, access, provider_map(number=IDS[1], section="Customer Info"))
    replaced = {**route(), "document_id": "d" * 32}
    capture(controller, access, provider_map(number=IDS[1], section="Customer Info", offset=2), replaced)
    report = report_maps(access, approval().session_id)
    assert report["captures"] == 4 and report["activation"] == "CANDIDATE_ONLY"
    assert [r["navigation"] for r in report["versions"]] == ["FIRST_OBSERVATION", "WORKSPACE_CHANGED", "DYNAMIC_SECTION_CHANGE", "DOCUMENT_REPLACED"]
    assert report["versions"][-1]["section_contract_version"] == 2
    carrier = next(p for p in report["cross_load_patterns"] if p["field"] == "carrier")
    assert carrier["presence_pattern"] == "POSSIBLY_OPTIONAL_OR_CONDITIONAL" and carrier["confidence"] == "PROPOSED"
    with access.database() as db:
        for table in ["runtime_mapping_sessions", "runtime_provider_maps"]:
            with pytest.raises(sqlite3.IntegrityError, match="append_only"):
                db.execute(f"DELETE FROM {table}")


@pytest.mark.parametrize("stop", ["revoke", "expiry", "pause", "bound"])
def test_mapping_lease_stops_and_bounds(runtime, stop):
    access, controller, now, *_ = runtime
    access.enable(mapping=approval(max_captures=1, minutes=1), owner_authorized=True)
    if stop == "revoke":
        access.disable(owner_authorized=True)
    elif stop == "expiry":
        now[0] += 61
    elif stop == "pause":
        access.set_paused(True, owner_authorized=True)
    else:
        capture(controller, access)
    with pytest.raises(PermissionError):
        access.request_mapping_capture(owner_authorized=True)


def test_in_flight_revoke_rejects_map_and_mapping_failure_has_no_retry(runtime):
    access, controller, *_ = runtime
    access.enable(mapping=approval(), owner_authorized=True)
    access.request_mapping_capture(owner_authorized=True)
    with pytest.raises(PermissionError, match="MAPPING_CAPTURE_PENDING"):
        access.request_mapping_capture(owner_authorized=True)
    d = wake(controller)
    controller.finish(result(d, session()))
    d = wake(controller)
    failed = controller.finish(result(d, None, "WORKSPACE_IDENTITY_CONFLICT"))
    assert failed["status"]["state"] == "STOPPED"
    assert failed["status"]["error_code"] == "WORKSPACE_IDENTITY_CONFLICT"
    assert "command" not in wake(controller)
    with access.database(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM runtime_provider_maps").fetchone()[0] == 0
    access.enable(mapping=MappingSessionApproval(**{**approval().model_dump(), "session_id": "owner-x1-mapping-fixture-02"}), owner_authorized=True)
    access.request_mapping_capture(owner_authorized=True)
    d = wake(controller)
    controller.finish(result(d, session()))
    d = wake(controller)
    access.disable(owner_authorized=True)
    with pytest.raises(PermissionError, match="READ_LEASE_REVOKED"):
        controller.finish(result(d, provider_map()))


@pytest.mark.parametrize("mutation", ["value", "unknown_label", "conflict", "writes", "different_child", "fingerprint", "promote"])
def test_metadata_host_contract_rejects_private_or_unverified_payload(mutation):
    value = provider_map()
    if mutation == "value":
        value["section"]["fields"][0]["value"] = "PRIVATE"
    elif mutation == "unknown_label":
        value["section"]["fields"][0]["semantic_label"] = "PRIVATE"
    elif mutation == "conflict":
        value["workspace"]["signals"][0]["load_id"] = IDS[1]
    elif mutation == "writes":
        value["writes_allowed"] = True
    elif mutation == "different_child":
        value["section"]["workspace_load_id"] = IDS[1]
    elif mutation == "fingerprint":
        value["section"]["fingerprint"] = "a" * 64
    else:
        value["section"]["fields"][0]["confidence"] = "VERIFIED"
    with pytest.raises(ValidationError):
        AscendProviderMap.model_validate(value)


def test_mapping_scope_and_view_skeletons():
    for ids in [["1755"], ["1", "1", "2"], ["1", "2", "SECRET"], ["1", "2", "Ãƒâ„¢Ã‚Â£"], [str(i) for i in range(6)]]:
        with pytest.raises(ValidationError):
            MappingSessionApproval(session_id=approval().session_id, approved_load_ids=ids)
    for write in ["SAVE", "SUBMIT", "ASCEND_UPDATE_LOAD", "ASCEND_READ_LOAD"]:
        with pytest.raises(ValidationError):
            MappingCommand(request_id="a" * 32, operation=write, approved_load_ids=IDS)
    assert len(OPERATIONAL_VIEW_SKELETONS) == 3
    assert all(v.status == "PREPARED_NOT_LIVE_VALIDATED" and v.workflow_semantics == "OWNER_ATTESTED_HYPOTHESIS" for v in OPERATIONAL_VIEW_SKELETONS)
    assert len(SCOPE["sections"]) == 13


def validate_cohort(access, controller):
    access.enable(mapping=approval(), owner_authorized=True)
    capture(controller, access)
    capture(controller, access, provider_map(section="Customer Info"))
    for number in IDS[1:]:
        capture(controller, access, provider_map(number=number))
    record_mapping_validation(access, approval().session_id, owner_authorized=True)


def normal_cycle(access, controller, evidence=None, *, hint=False):
    dispatch = wake(controller, mapping_hint=hint)
    if "command" in dispatch and dispatch["command"]["operation"] == "ASCEND_GET_SESSION_STATE":
        controller.finish(result(dispatch, session()))
        dispatch = wake(controller, mapping_hint=hint)
    assert dispatch["command"]["operation"] == "ASCEND_MAP_WORKSPACE"
    assert dispatch["command"]["owner_present"] is True
    return controller.finish(result(dispatch, evidence or provider_map()))


def test_normal_mode_requires_validation_then_follows_owner_without_id_list(runtime):
    access, controller, now, *_ = runtime
    normal = MappingSessionApproval(session_id="owner-x1-mapping-normal-fixture-01", mode="NORMAL_OWNER_PRESENT")
    assert normal.approved_load_ids is None
    with pytest.raises(PermissionError, match="MAPPING_VALIDATION_REQUIRED"):
        access.enable(mapping=normal.model_copy(update={"operation_mode": "AUTO_MAP"}), owner_authorized=True)
    assert not access.status()["mapping_mode"]
    with pytest.raises(PermissionError, match="OWNER_REQUIRED"):
        record_mapping_validation(access, approval().session_id)
    validate_cohort(access, controller)
    access.enable(mapping=normal, owner_authorized=True)
    first = normal_cycle(access, controller)
    assert first["status"]["mapping_section_count"] == 1
    now[0] += 3
    repeated = normal_cycle(access, controller, provider_map(at=now[0]), hint=True)
    assert repeated["status"]["mapping_section_count"] == 1
    # A genuinely different owner-opened workspace needs no pre-enumerated ID.
    now[0] += 3
    changed = normal_cycle(access, controller, provider_map(number="999123", at=now[0]), hint=True)
    assert changed["status"]["mapping_workspace_count"] == 2
    assert changed["status"]["mapping_last_summary"]["load_id"] == "999123"
    report = report_maps(access, normal.session_id)
    assert report["captures"] == 2 and report["versions"][-1]["navigation"] == "WORKSPACE_CHANGED"
    assert not report["live_validated"]


@pytest.mark.parametrize("bound,code", [("max_workspace_captures", "MAPPING_WORKSPACE_BOUND"),
    ("max_section_observations", "MAPPING_SECTION_BOUND"), ("max_contract_observations", "MAPPING_CONTRACT_BOUND")])
def test_normal_category_budgets_fail_closed(runtime, bound, code):
    access, controller, now, *_ = runtime
    validate_cohort(access, controller)
    normal = MappingSessionApproval(session_id="owner-x1-mapping-normal-fixture-01", mode="NORMAL_OWNER_PRESENT", **{bound: 1})
    access.enable(mapping=normal, owner_authorized=True)
    normal_cycle(access, controller)
    now[0] += 3
    stopped = normal_cycle(access, controller, provider_map(number="999123", at=now[0]), hint=True)
    assert stopped["status"]["error_code"] == code and stopped["status"]["state"] == "STOPPED"
    assert report_maps(access, normal.session_id)["captures"] == 1


def test_normal_optional_stricter_scope_and_owner_presence(runtime):
    access, controller, *_ = runtime
    validate_cohort(access, controller)
    normal = MappingSessionApproval(session_id="owner-x1-mapping-normal-fixture-01", mode="NORMAL_OWNER_PRESENT", approved_load_ids=["1755"])
    access.enable(mapping=normal, owner_authorized=True)
    value = provider_map()
    value["owner_present"] = False
    stopped = normal_cycle(access, controller, value)
    assert stopped["status"]["error_code"] == "WORKSPACE_SCOPE_DENIED"
    assert report_maps(access, normal.session_id)["captures"] == 0


def test_signed_mapping_capture_requires_existing_lease(enrollment, monkeypatch):
    from executors.ascend_extension.runtime import RuntimeAccess, RuntimeController
    from tests.test_ascend_x1_enrollment import enroll, envelope
    from uuid import uuid4
    host, _, package = enroll(enrollment)
    repo = enrollment.repo
    kwargs = dict(enrollment_guard=enrollment.load, gate=lambda _: None, clock=enrollment.clock)
    access, controller = RuntimeAccess(repo, **kwargs), RuntimeController(repo, **kwargs)
    monkeypatch.setattr(host, "_runtime", lambda: controller)
    body = {"kind": "RUNTIME_MAPPING_CAPTURE", "request_id": uuid4().hex}
    denied = host.handle(envelope(host, package["key"], body))["envelope"]["body"]
    assert denied["status"]["error_code"] == "READ_ACCESS_DISABLED"
    access.enable(mapping=approval(), owner_authorized=True)
    queued = host.handle(envelope(host, package["key"], {**body, "request_id": uuid4().hex}, sequence=2))["envelope"]["body"]
    assert queued["status"]["mapping_capture_requested"] is True
    assert queued["kind"] == "RUNTIME_STATUS" and queued["production_writes"] is False


def test_context_unknown_until_separate_validation_and_fresh_identity():
    m = AscendProviderMap.model_validate(provider_map())
    f = m.section.fields[0]
    assembler = VerifiedAscendLoadContextAssembler()
    observation = VerifiedProviderObservation("1755", "equipment", "equipment", f.contract_fingerprint, "SYNTHETIC", 1000)
    result = assembler.assemble(m, [m], [observation], [], now=1001)
    assert result["identity"]["value"] == "1755" and result["equipment"]["confidence"] == "UNKNOWN"
    with pytest.raises(PermissionError):
        ReadMappingValidation.controlled_comparison(f, "fixture")
    validation = ReadMappingValidation.controlled_comparison(f, "fixture", matched=True, owner_authorized=True)
    result = assembler.assemble(m, [m], [observation], [validation], now=1001)
    assert result["equipment"]["confidence"] == "VERIFIED"
    assert result["financials"]["confidence"] == "UNKNOWN"
    stale = assembler.assemble(m, [m], [observation], [validation], now=2000)
    assert all(v["confidence"] == "UNKNOWN" for v in stale.values())
    changed = AscendProviderMap.model_validate(provider_map(number=IDS[1]))
    assert assembler.assemble(changed, [m], [observation], [validation], now=1001)["equipment"]["confidence"] == "UNKNOWN"
    drift = AscendProviderMap.model_validate(provider_map(at=1001, offset=2))
    assert assembler.assemble(drift, [m, drift], [observation], [validation], now=1002)["equipment"]["confidence"] == "UNKNOWN"
    weak = AscendProviderMap.model_validate(provider_map(level="LEVEL_3")).section.fields[0]
    with pytest.raises(PermissionError):
        ReadMappingValidation.controlled_comparison(weak, "fixture", matched=True, owner_authorized=True)


def test_workspace_dom_fixtures_and_reader_integration(tmp_path):
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel="msedge", headless=True, env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)})
            context = await browser.new_context(service_workers="block")
            await context.route("**/*", lambda r: r.fulfill(content_type="text/html", body="<title>Offline fixture</title>"))
            page = await context.new_page()
            try:
                await page.goto("https://ascendtms.com/loads")
                for file in ["contract.js", "read-errors.js", "load-board-view.js", "detail-scope.js", "webbridge.js", "mapping-scope.js", "workspace.js", "reader.js"]:
                    await page.add_script_tag(path=str(EXT / file))
                nav = '<nav>' + ''.join(f'<a href="#">{s}</a>' for s in ["Dashboard", "Loads", "Customers", "Carriers"]) + '</nav>'
                def html(number="1755", section="Load Basics", fields=None, header=None):
                    fields = fields if fields is not None else '<label for="f">Equipment</label><input id="f" value="PRIVATE_EQUIPMENT" data-private-secret="PRIVATE_TOKEN">'
                    return nav + '<main id="workspace">' + (header or f'<h1>Load #{number}</h1>') + '<div role="tablist">' + ''.join(
                        f'<button id="tab{i}" role="tab" aria-selected="{str(s == section).lower()}" aria-controls="panel">{s}</button>'
                        for i, s in enumerate(["Load Basics", "Customer Info", section] if section not in ["Load Basics", "Customer Info"] else ["Load Basics", "Customer Info"])) + f'</div><section id="panel" role="tabpanel"><h2>{section}</h2>{fields}<button>Save</button></section></main>'
                async def observe(body):
                    await page.evaluate("body=>document.body.innerHTML=body", body)
                    return await page.evaluate("""async ids=>{
                        try{const reader=await FreightDeskX1Reader.create(document,location.origin);
                          const command={version:1,request_id:'a'.repeat(32),operation:'ASCEND_MAP_WORKSPACE',load_id:null,expected_revision:null,tenant_id:'booking-logistics',actor:'FreightDesk/Avery',approved_load_ids:ids,owner_present:false,lease_expires_at:Date.now()/1000+60};
                          return {map:await reader.executeRuntime(command,()=>{})};
                        }catch(e){return {error:FreightDeskReadErrors.safe(e)}}
                    }""", IDS)
                for nonload in ['Location Profile', 'Customer Profile', 'Carrier Profile', 'Dashboard', 'Active Loads']:
                    stopped = await observe(nav + '<main><h1>'+nonload+'</h1><table><tr><td>PRIVATE</td></tr></table></main>')
                    assert stopped == {"error": "NOT_A_LOAD_WORKSPACE"}
                noisy = await observe('<aside>' + '<a>Unrelated navigation</a>' * 1000 + '</aside>' + html())
                assert "map" in noisy and "PRIVATE" not in json.dumps(noisy)
                agreed = await observe(html(header='<h1>Load #1755</h1><nav aria-label="breadcrumb"><a>Load #1755</a></nav>'))
                assert len(agreed["map"]["workspace"]["signals"]) == 2
                first = await observe(html())
                assert "map" in first, first
                AscendProviderMap.model_validate(first["map"])
                field = first["map"]["section"]["fields"][0]
                assert field["field_name_candidate"] == "equipment" and field["evidence_level"] == "LEVEL_2"
                assert field["confidence"] == "PROPOSED" and field["locator_graph"]["data_attribute_names"] == ["data-unclassified"]
                assert "PRIVATE" not in json.dumps(first)
                stages = await page.evaluate("""async ids=>{
                  const stages=[];await FreightDeskWorkspace.capture(document,ids,()=>{},d=>stages.push(d));return stages;
                }""", IDS)
                assert [d["stage"] for d in stages] == ["ENTITY_DISCOVERY", "LOAD_WORKSPACE_CANDIDATE_FOUND", "WORKSPACE_IDENTITY_VERIFIED", "SECTION_IDENTIFIED", "STRUCTURE_CAPTURED"]
                assert stages[-1]["candidate_workspace_count"] == 1
                assert "PRIVATE" not in json.dumps(stages)
                timed = await page.evaluate("""async ids=>{let last=null;try{
                  await FreightDeskWorkspace.capture(document,ids,()=>{if(last?.stage==='SECTION_IDENTIFIED')throw Error('READ_TIMEOUT');},d=>last=d);
                }catch(e){return {code:e.message,last};}}""", IDS)
                assert timed["code"] == "READ_TIMEOUT" and timed["last"]["stage"] == "SECTION_IDENTIFIED"
                limited = await page.evaluate("""async ids=>{try{await FreightDeskWorkspace.capture(document,ids,()=>{},()=>{},performance.now(),{capture_load_id:'900001',capture_section:'Load Basics'});return 'BAD';}catch(e){return e.message;}}""", IDS)
                assert limited == "EXPECTED_LOAD_NOT_OPEN"
                await page.evaluate("body=>document.body.innerHTML=body", html(section="Customer Info"))
                wrong_section = await page.evaluate("""async ids=>{try{await FreightDeskWorkspace.capture(document,ids,()=>{},()=>{},performance.now(),{capture_load_id:'1755',capture_section:'Load Basics'});return 'BAD';}catch(e){return e.message;}}""", IDS)
                assert wrong_section == "STARTING_SECTION_MISMATCH"
                await page.evaluate("body=>document.body.innerHTML=body", html())

                breadcrumb = await observe(html(header='<nav aria-label="breadcrumb"><a>Load #1755</a></nav>'))
                assert breadcrumb["map"]["workspace"]["signals"][0]["kind"] == "BREADCRUMB"
                conflict = await observe(html(header='<h1>Load #1755</h1><h2>Load #900001</h2>'))
                assert conflict["error"] == "WORKSPACE_IDENTITY_CONFLICT"
                child = await observe(html(section="Customer Info"))
                assert child["map"]["workspace"]["load_id"] == "1755"
                assert child["map"]["section"]["identity_source"] == "INHERITED_FROM_REVALIDATED_WORKSPACE"
                changed = await observe(html(number=IDS[1]))
                assert changed["map"]["workspace"]["load_id"] == IDS[1]
                assert (await observe(html(number="555555")))["error"] == "WORKSPACE_SCOPE_DENIED"
                missing = html(header='<h1>Workspace</h1>').replace('<h2>Load Basics</h2>', '<h2>Load #1755</h2>')
                assert (await observe(missing))["error"] == "WORKSPACE_IDENTITY_MISSING"
                unclassified = await observe(html(section="PRIVATE_NEW_SECTION", fields='<input aria-label="PRIVATE_PHONE" value="PRIVATE_PHONE_VALUE">'))
                assert unclassified["map"]["section"]["section"] == "DISCOVERED_UNCLASSIFIED"
                assert unclassified["map"]["section"]["fields"][0]["field_name_candidate"] == "UNKNOWN"
                assert "PRIVATE" not in json.dumps(unclassified)
                unknown = await observe(html(fields='<label for="f">Carrier</label><input id="f" aria-label="Driver" value="PRIVATE">'))
                assert unknown["map"]["section"]["fields"][0]["confidence"] == "UNKNOWN"
                unknown = await observe(html(fields='<input data-field="carrier" aria-label="PRIVATE_MEANING" value="PRIVATE">'))
                assert unknown["map"]["section"]["fields"][0]["confidence"] == "UNKNOWN"
                strong = await observe(html(fields='<input data-field="equipment" readonly value="PRIVATE">'))
                assert strong["map"]["section"]["fields"][0]["evidence_level"] == "LEVEL_1"
                assert not strong["map"]["section"]["fields"][0]["editable"]
                absent = await observe(html(fields=''))
                assert absent["map"]["section"]["fields"] == []
                drift = await observe(html(fields='<span></span><label for="new-f">Equipment</label><input id="new-f" value="PRIVATE">'))
                drift_field = drift["map"]["section"]["fields"][0]
                assert drift_field["contract_fingerprint"] != field["contract_fingerprint"]
                remap = await page.evaluate("([a,b])=>FreightDeskWebBridge.AdaptiveLocator.proposeMapping(a,b)", [field, drift_field])
                assert remap["activation"] == "CANDIDATE_ONLY" and not remap["writes_allowed"]
                for section in SCOPE["sections"]:
                    observed = await observe(html(section=section))
                    AscendProviderMap.model_validate(observed["map"])
                # Dynamic section navigation does not need a repeated load ID in the panel.
                await observe(html())
                await page.evaluate("""()=>{document.querySelector('#tab0').setAttribute('aria-selected','false');document.querySelector('#tab1').setAttribute('aria-selected','true');document.querySelector('#panel h2').textContent='Customer Info';}""")
                dynamic = await page.evaluate("ids=>FreightDeskWorkspace.capture(document,ids,()=>{})", IDS)
                assert dynamic["section"]["section"] == "Customer Info" and dynamic["workspace"]["load_id"] == "1755"
                # Mid-capture identity change is rejected, never inherited from a stale workspace proof.
                await observe(html())
                mutation = await page.evaluate("""async ids=>{setTimeout(()=>document.querySelector('h1').textContent='Load #900001',30);
                  try{await FreightDeskWorkspace.capture(document,ids,()=>{});return 'BAD'}catch(e){return e.message}}""", IDS)
                assert mutation == "WORKSPACE_CHANGED"
                # No interaction or value accessor is needed by the sensor.
                await observe(html())
                await page.evaluate("""()=>{window.clicks=0;document.addEventListener('click',()=>window.clicks++);
                    Object.defineProperty(HTMLInputElement.prototype,'value',{get(){throw Error('PRIVATE_VALUE_READ')}});
                    window.fetch=()=>{throw Error('NETWORK_NOT_ALLOWED')};window.XMLHttpRequest=()=>{throw Error('NETWORK_NOT_ALLOWED')};}""")
                safe = await page.evaluate("ids=>FreightDeskWorkspace.capture(document,ids,()=>{})", IDS)
                assert not safe["values_included"] and await page.evaluate("window.clicks") == 0
                await page.evaluate("()=>document.querySelector('h1').textContent='Load #999123'")
                normal = await page.evaluate("()=>FreightDeskWorkspace.capture(document,null,()=>{})")
                assert normal["workspace"]["load_id"] == "999123" and normal["workspace"]["entity_type"] == "LOAD"
                # Current-workspace hints carry no DOM content and stop when the private port closes.
                await page.add_script_tag(path=str(EXT / "build.js"))
                await page.evaluate("""()=>{window.chrome={runtime:{id:'a'.repeat(32),getManifest:()=>({version:FreightDeskBuild.extension_version}),
                  onConnect:{addListener(fn){window.connect=fn},removeListener(){}},onMessage:{addListener(){}}}};
                  window.portMessages=[];window.fixturePort={name:'freightdesk-x1-identity',sender:{id:'a'.repeat(32)},
                    postMessage(m){portMessages.push(m)},onDisconnect:{addListener(fn){window.closeFixturePort=fn}},
                    onMessage:{addListener(fn){window.portMessage=fn}},disconnect(){window.closeFixturePort?.()}};}""")
                await page.add_script_tag(path=str(EXT / "content.js"))
                await page.evaluate("""()=>{connect(fixturePort);const ready=portMessages[0];portMessage({kind:'X1_RUNTIME_DISPATCH_V2',
                  document_id:ready.document_id,document_generation:ready.document_generation,deadline:Date.now()/1000+10,
                  command:{version:1,request_id:'b'.repeat(32),operation:'ASCEND_MAP_WORKSPACE',load_id:null,expected_revision:null,
                    tenant_id:'booking-logistics',actor:'FreightDesk/Avery',approved_load_ids:null,owner_present:true,lease_expires_at:Date.now()/1000+60}})}""")
                await page.wait_for_function("portMessages.some(m=>m.kind==='X1_RESULT_V2')")
                assert await page.evaluate("portMessages.find(m=>m.kind==='X1_RESULT_V2').error_code") is None
                await page.evaluate("()=>document.querySelector('h1').firstChild.data='Load #999124'")
                await page.wait_for_function("portMessages.some(m=>m.kind==='X1_MAPPING_CHANGED_V1')", timeout=4000)
                hint = await page.evaluate("portMessages.find(m=>m.kind==='X1_MAPPING_CHANGED_V1')")
                assert set(hint) == {"kind", "document_id", "document_generation"}
                await page.evaluate("()=>{closeFixturePort();document.querySelector('h1').textContent='Load #999125'}")
                await page.wait_for_timeout(2200)
                assert await page.evaluate("portMessages.filter(m=>m.kind==='X1_MAPPING_CHANGED_V1').length") == 1
            finally:
                await context.close()
                await browser.close()
    asyncio.run(run())
