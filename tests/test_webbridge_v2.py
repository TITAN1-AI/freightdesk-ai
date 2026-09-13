"""V2 offline contracts, synthetic DOM and atomic evidence. All requests are intercepted.

No installed extension/profile, tenant databases, native host or provider execution.
"""
import asyncio
import copy
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from executors.webbridge_v2.contracts import Binding, validate_graph
from executors.webbridge_v2.store import OfflineObservationStore

ROOT = Path(__file__).resolve().parents[1]
VOCABULARY = frozenset({"Load Basics", "Customer Info", "Equipment", "Carrier", "Save", "Overview", "Contacts"})

SETUP = r"""({scenario}) => {
  document.body.innerHTML='<nav id="chrome"></nav><main id="work" data-load-id="900101">'+
    '<h1>Load #900101</h1><div role="tablist">'+
    '<button role="tab" id="t1" aria-selected="true" aria-controls="p1">Load Basics</button>'+
    '<button role="tab" aria-controls="p2" aria-selected="false">Customer Info</button></div>'+
    '<section role="tabpanel" id="p1"><h2>Load Basics</h2><form><label for="f">Equipment</label>'+
    '<input id="f" value="PRIVATE_VALUE"><div data-private>PRIVATE_NOTE</div><button>Save</button></form></section>'+
    '<section role="tabpanel" id="p2" hidden><h2>Customer Info</h2></section></main>';
  const root=document.getElementById('work'), tab=document.getElementById('t1'), panel=document.getElementById('p1');
  const state={schemaVersion:2,document,root,epoch:'document-1',realm:'realm-1',leaseRef:'lease-1',sessionRef:'session-1',
    provider:'AscendTMS',entityType:'LOAD',entityId:'900101',identityVerified:true,ownerPresent:true,foreground:true,
    sessionVerified:true,leaseValid:true,revoked:false};
  const limits={}; let onYield=()=>{}, clock=()=>performance.now();
  switch(scenario) {
    case 'chrome': document.getElementById('chrome').innerHTML='<div></div>'.repeat(5000);break;
    case 'duplicate_target': panel.insertAdjacentHTML('afterend','<section id="p1"><h2>Load Basics</h2></section>');break;
    case 'missing_target': tab.setAttribute('aria-controls','outside');break;
    case 'outside_target': document.body.insertAdjacentHTML('beforeend','<section id="outside"><h2>Load Basics</h2></section>');tab.setAttribute('aria-controls','outside');break;
    case 'multiple_targets': document.getElementById('p2').hidden=false;tab.setAttribute('aria-controls','p1 p2');break;
    case 'no_selection': tab.setAttribute('aria-selected','false');break;
    case 'two_selected': root.querySelectorAll('[role=tab]')[1].setAttribute('aria-selected','true');break;
    case 'wrong_heading': panel.querySelector('h2').textContent='Customer Info';break;
    case 'hidden_panel': panel.hidden=true;break;
    case 'unknown_label': tab.textContent='PRIVATE_CUSTOMER';break;
    case 'label_conflict': panel.insertAdjacentHTML('beforeend','<label for="f">Carrier</label>');break;
    case 'hidden_label': panel.querySelector('label').hidden=true;break;
    case 'aria_label': document.getElementById('f').setAttribute('aria-label','Equipment');break;
    case 'private_aria': document.getElementById('f').setAttribute('aria-label','PRIVATE_CONTACT');break;
    case 'unknown_workspace': state.identityVerified=false;break;
    case 'wrong_origin': state.origin='https://elsewhere.invalid';break;
    case 'missing_presence': state.ownerPresent=false;clock=()=>{throw Error('CLOCK_MUST_NOT_START');};break;
    case 'background': state.foreground=false;break;
    case 'hidden_workspace': root.hidden=true;clock=()=>{throw Error('CLOCK_MUST_NOT_START');};break;
    case 'session_missing': state.sessionVerified=false;break;
    case 'lease_expired': state.leaseValid=false;break;
    case 'revoked': state.revoked=true;break;
    case 'string_boolean': state.sessionVerified='true';break;
    case 'schema_mismatch': state.schemaVersion=1;break;
    case 'large_root': root.insertAdjacentHTML('beforeend','<div></div>'.repeat(100));limits.visited=20;break;
    case 'emitted_bound': limits.emitted=5;break;
    case 'depth_bound': panel.innerHTML='<div><div><div><div></div></div></div></div>';limits.depth=3;break;
    case 'attribute_bound': tab.setAttribute('data-one','x');limits.attributes=4;break;
    case 'reference_bound': tab.setAttribute('aria-controls','a b c');limits.references=2;break;
    case 'payload_bound': limits.payloadBytes=100;break;
    case 'label_bound': tab.innerHTML='<span>L</span>'.repeat(20);limits.labelNodes=4;break;
    case 'deadline': {let t=0;clock=()=>++t*5;limits.elapsedMs=2;break;}
    case 'document_changed': limits.batch=1;onYield=()=>{state.epoch='document-2';};break;
    case 'realm_changed': limits.batch=1;onYield=()=>{state.realm='realm-2';};break;
    case 'lease_changed': limits.batch=1;onYield=()=>{state.leaseRef='lease-2';};break;
    case 'load_changed': limits.batch=1;onYield=()=>{state.entityId='900102';};break;
    case 'revoke_during': limits.batch=1;onYield=()=>{state.revoked=true;};break;
    case 'mutated': limits.batch=1;onYield=()=>{tab.setAttribute('aria-selected','false');};break;
    case 'unexpected': limits.batch=1;onYield=()=>{throw Error('PRIVATE_ERROR');};break;
    case 'shadow': {const host=document.createElement('x-fixture');root.append(host);host.innerHTML='<button slot="s">Carrier</button>';
      host.attachShadow({mode:'open'}).innerHTML='<div style="display:contents"><slot name="s"></slot><label>Equipment</label></div>';break;}
    case 'frame': panel.insertAdjacentHTML('beforeend','<iframe></iframe>');break;
    case 'sibling': root.innerHTML='<h1>Load #900101</h1><div><div><h1>Load Basics</h1></div><ul><li class="active"><a href="/loads">Load Basics</a></li>'+
      '<li><a href="/other">Customer Info</a></li></ul><div><form><label for="f">Equipment</label><input id="f"></form></div></div>';break;
    case 'nested_value': tab.innerHTML='Load Basics<input value="PRIVATE_NESTED">';break;
    case 'portal': panel.remove();document.body.append(panel);break;
    case 'private_id': document.getElementById('f').id='PRIVATE_IDENTIFIER';root.querySelector('label').htmlFor='PRIVATE_IDENTIFIER';break;
    case 'closed_root': {const host=document.createElement('x-closed');root.append(host);host.attachShadow({mode:'closed'}).innerHTML='<p>PRIVATE_SHADOW</p>';break;}
    case 'display_contents': panel.style.display='contents';break;
    case 'cyclic_refs': tab.setAttribute('aria-owns','p1');panel.setAttribute('aria-owns','t1');break;
    case 'multi_label_refs': panel.insertAdjacentHTML('beforeend','<label id="label2">Equipment</label>');document.getElementById('f').setAttribute('aria-labelledby','label2 label2');break;
    case 'table_private': panel.insertAdjacentHTML('beforeend','<table><tr><td>PRIVATE_TABLE</td></tr></table>');break;
    case 'generic_sibling': state.provider='GenericFixture';root.innerHTML='<h1>Item 900101</h1><div><div><h1>Overview</h1></div><ul><li class="active"><a href="/loads">Overview</a></li><li><a href="/other">Contacts</a></li></ul><div><form><label>Equipment</label><input></form></div></div>';break;
    case 'two_form_regions': root.innerHTML='<h1>Load #900101</h1><div><h2>Load Basics</h2><ul><li class="active"><a href="/loads">Load Basics</a></li></ul><div><form><input></form></div><div><form><input></form></div></div>';break;
  }
  // Tripwires cover getters and writes, not merely absence of values from serialized output.
  for(const e of root.querySelectorAll('input,select,textarea')) for(const key of ['value','textContent','innerText','selectedOptions','checked'])
    Object.defineProperty(e,key,{get(){throw Error('PRIVATE_ACCESS');}});
  for(const e of root.querySelectorAll('[data-private]')) Object.defineProperty(e,'textContent',{get(){throw Error('PRIVATE_ACCESS');}});
  for(const e of root.querySelectorAll('td,th')) Object.defineProperty(e,'textContent',{get(){throw Error('PRIVATE_ACCESS');}});
  root.click=()=>{throw Error('WRITE_ATTEMPT');};
  for(const e of root.querySelectorAll('button,a,form')) {e.click=()=>{throw Error('WRITE_ATTEMPT');};e.submit=()=>{throw Error('WRITE_ATTEMPT');};}
  globalThis.fixtureState=state;
  globalThis.fixtureV2=FreightDeskWebBridgeV2.createOfflineHarness({mode:'OFFLINE',origin:state.origin||location.origin,
    readProof:()=>state,vocabulary:['Load Basics','Customer Info','Equipment','Carrier','Save','Overview','Contacts'],sections:['Load Basics','Customer Info','Overview','Contacts'],
    stateClasses:['active'],limits,clock,yieldControl:async()=>{onYield();}});
}"""

CASES = {
    "display_contents": None, "cyclic_refs": None, "multi_label_refs": None, "table_private": None, "generic_sibling": None, "two_form_regions": None,
    "baseline": None, "chrome": None, "duplicate_target": None, "missing_target": None,
    "outside_target": None, "multiple_targets": None, "no_selection": None, "two_selected": None,
    "wrong_heading": None, "hidden_panel": None, "unknown_label": None, "label_conflict": None,
    "hidden_label": None, "aria_label": None, "private_aria": None, "private_id": None,
    "shadow": None, "frame": None, "sibling": None, "nested_value": None, "portal": None, "closed_root": None,
    "unknown_workspace": "V2_IDENTITY_UNVERIFIED", "wrong_origin": "V2_ORIGIN_MISMATCH",
    "missing_presence": "WAITING_FOR_OWNER_WORKSPACE", "background": "WAITING_FOR_OWNER_WORKSPACE",
    "hidden_workspace": "WAITING_FOR_OWNER_WORKSPACE", "session_missing": "V2_SESSION_UNVERIFIED",
    "lease_expired": "V2_AUTHORITY_UNAVAILABLE", "revoked": "V2_AUTHORITY_UNAVAILABLE",
    "string_boolean": "V2_SESSION_UNVERIFIED", "schema_mismatch": "V2_PROTOCOL_MISMATCH",
    "large_root": "V2_BOUND_EXCEEDED", "emitted_bound": "V2_BOUND_EXCEEDED", "depth_bound": "V2_BOUND_EXCEEDED",
    "attribute_bound": "V2_BOUND_EXCEEDED", "reference_bound": "V2_BOUND_EXCEEDED", "payload_bound": "V2_BOUND_EXCEEDED",
    "label_bound": "V2_BOUND_EXCEEDED", "deadline": "V2_BOUND_EXCEEDED",
    "document_changed": "V2_DOCUMENT_CHANGED", "realm_changed": "V2_DOCUMENT_CHANGED",
    "lease_changed": "V2_BINDING_CHANGED", "load_changed": "V2_IDENTITY_CHANGED",
    "revoke_during": "V2_AUTHORITY_UNAVAILABLE", "mutated": "V2_STRUCTURE_CHANGED", "unexpected": "V2_CAPTURE_FAILED",
}


@pytest.fixture(scope="module")
def captures(tmp_path_factory):
    temp = tmp_path_factory.mktemp("webbridge-v2-browser")

    async def run():
        from playwright.async_api import async_playwright
        output = {}
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel="msedge", headless=True,
                env={**os.environ, "TEMP": str(temp), "TMP": str(temp)})
            context = await browser.new_context(service_workers="block")
            await context.route("**/*", lambda route: route.fulfill(content_type="text/html", body="<title>Offline fixture</title>"))
            page = await context.new_page()
            try:
                await page.goto("https://fixture.invalid/loads")
                await page.add_script_tag(path=str(ROOT / "extensions/webbridge-v2/semantics.js"))
                await page.add_script_tag(path=str(ROOT / "extensions/webbridge-v2/core.js"))
                for scenario in CASES:
                    await page.evaluate(SETUP, {"scenario": scenario})
                    result = await page.evaluate("async()=>{const result=await fixtureV2.capture('fixture-observation');return {result,section:result.graph?fixtureV2.section(result.graph):null};}")
                    output[scenario] = result
                    await page.evaluate("fixtureV2.close()")
                await page.evaluate(SETUP, {"scenario": "baseline"})
                output["lifecycle"] = await page.evaluate("""async()=>{
                  const a=await fixtureV2.capture('one'); const b=await fixtureV2.capture('two');
                  fixtureState.sessionRef='session-2';const c=await fixtureV2.capture('three');
                  fixtureState.epoch='document-2';const d=await fixtureV2.capture('four');
                  fixtureV2.close();const e=await fixtureV2.capture('five');
                  return {same:a.graph.root===b.graph.root,refresh:b.graph.root===c.graph.root,
                    new_epoch:c.graph.root!==d.graph.root,closed:e.error_code,frozen:Object.isFrozen(a.graph.nodes[0])};
                }""")
            finally:
                await browser.close()
        (temp / 'measurements.json').write_text(json.dumps({name: value['result']['measurements']
            for name, value in output.items() if name != 'lifecycle'}, indent=2), encoding='utf-8')
        return output
    return asyncio.run(run())


@pytest.mark.parametrize("scenario,code", CASES.items())
def test_bounded_offline_capture(captures, scenario, code):
    result = captures[scenario]["result"]
    assert result.get("error_code") == code
    assert result["status"] == ("STOPPED" if code else "CAPTURED")
    assert not any(secret in json.dumps(result) for secret in [
        "PRIVATE_VALUE", "PRIVATE_NOTE", "PRIVATE_CUSTOMER", "PRIVATE_CONTACT", "PRIVATE_IDENTIFIER",
        "PRIVATE_NESTED", "PRIVATE_SHADOW", "PRIVATE_ERROR", "PRIVATE_ACCESS", "PRIVATE_TABLE",
    ])
    assert result["values_included"] is False and result["production_writes"] is False
    if code:
        assert "graph" not in result
    else:
        validate_graph(result["graph"], expected_binding=Binding.model_validate(result["graph"]["binding"]), vocabulary=VOCABULARY)


@pytest.mark.parametrize("scenario", ["duplicate_target", "missing_target", "outside_target", "multiple_targets", "no_selection", "two_selected", "wrong_heading", "hidden_panel", "unknown_label", "nested_value", "portal", "two_form_regions"])
def test_section_ambiguity_stops(captures, scenario):
    assert captures[scenario]["section"]["status"] == "UNVERIFIED"
    assert captures[scenario]["section"]["failed_predicate"]


def test_privacy_relationships_and_lifecycle(captures):
    base = captures["baseline"]["result"]
    assert captures["baseline"]["section"]["status"] == "VERIFIED"
    assert captures["sibling"]["section"]["derived_relation"]["kind"] == "SIBLING_FORM_REGION"
    assert captures["generic_sibling"]["section"]["section"] == "Overview"
    assert captures["generic_sibling"]["section"]["derived_relation"]["kind"] == "SIBLING_FORM_REGION"
    assert captures["display_contents"]["section"]["status"] == "VERIFIED"
    assert captures["chrome"]["result"]["measurements"]["visited"] == base["measurements"]["visited"]
    assert captures["missing_presence"]["result"]["measurements"]["elapsed_ms"] == 0
    assert captures["hidden_workspace"]["result"]["measurements"]["elapsed_ms"] == 0
    assert any(r["kind"] == "SLOT_ASSIGNED" for r in captures["shadow"]["result"]["graph"]["relations"])
    assert "FRAME_UNOBSERVED" in captures["frame"]["result"]["graph"]["coverage"]["gaps"]
    assert "SHADOW_AVAILABILITY_UNKNOWN" in captures["closed_root"]["result"]["graph"]["coverage"]["gaps"]
    assert any(n["name_conflict"] for n in captures["label_conflict"]["result"]["graph"]["nodes"])
    assert captures["lifecycle"] == {"same": True, "refresh": True, "new_epoch": True, "closed": "V2_CLOSED", "frozen": True}
    bound = captures["large_root"]["result"]["bound"]
    assert bound == {"category": "visited", "measured": 21, "maximum": 20}
    assert captures["deadline"]["result"]["last_completed_stage"] == "BOUNDARY_VERIFIED"


def test_atomic_store_and_rejected_payloads(captures, tmp_path):
    graph = captures["baseline"]["result"]["graph"]
    binding = Binding.model_validate(graph["binding"])
    store = OfflineObservationStore(tmp_path / "observations.sqlite3")
    args = {"expected_binding": binding, "vocabulary": VOCABULARY}
    first = store.persist(graph, **args)
    assert first["status"] == "GRAPH_PERSISTED" and first["duplicate"] is False
    assert store.persist(graph, **args)["duplicate"] is True
    wrong = copy.deepcopy(graph)
    wrong["nodes"][0]["attributes"] = []
    with pytest.raises(PermissionError, match="^V2_OBSERVATION_CONFLICT$"):
        store.persist(wrong, **args)
    failed = copy.deepcopy(graph)
    failed["observation_id"] = "failed"
    failed["observation_binding"]["observation_id"] = "failed"
    for item in failed["evidence"]:
        item["observation_id"] = "failed"
    def fail():
        raise RuntimeError("PRIVATE_DATABASE_ERROR")
    with pytest.raises(RuntimeError, match="^V2_PERSIST_FAILED$"):
        store.persist(failed, before_receipt=fail, **args)
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM observations").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 1
    for modify in [
        lambda d: d.update(values_included=True), lambda d: d.update(values_included=0),
        lambda d: d.update(production_writes=True), lambda d: d.update(schema_version=3),
        lambda d: d["nodes"][0].update(value="PRIVATE"), lambda d: d["nodes"][0].update(name="PRIVATE"),
        lambda d: d["nodes"][0].update(parent=d["root"]), lambda d: d["nodes"][1].update(id=d["root"]),
        lambda d: d["binding"].update(lease_ref="other"), lambda d: d["relations"][0].update(to="g9n9"),
        lambda d: d["nodes"][0].update(action_effect="READ_ONLY_NAVIGATION"),
    ]:
        bad = copy.deepcopy(graph)
        modify(bad)
        with pytest.raises(PermissionError, match="^V2_GRAPH_REJECTED$"):
            store.persist(bad, **args)
    parsed = validate_graph(graph, **args)
    assert isinstance(parsed.nodes, tuple)
    with pytest.raises(ValidationError):
        parsed.nodes[0].name = "Carrier"


def test_no_production_registration_or_store(tmp_path):
    manifest = json.loads((ROOT / "extensions/ascend-x1/manifest.json").read_text())
    assert "webbridge-v2" not in json.dumps(manifest)
    with pytest.raises(PermissionError, match="V2_OFFLINE_STORE_ONLY"):
        OfflineObservationStore(ROOT / "forbidden.sqlite3")
    assert not (ROOT / "forbidden.sqlite3").exists()
