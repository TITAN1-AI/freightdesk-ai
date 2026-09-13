"""Synthetic section-proof diagnostics; all browser requests intercepted offline."""
import asyncio
import json
import os
from uuid import uuid4

import pytest
from pydantic import ValidationError

from executors.ascend_extension.mapping_diagnostics import MappingDiagnostic, MappingSectionDiagnostic
from tests.test_ascend_x1_dom import EXT
from tests.test_ascend_x1_controller import repo as repo, session
from tests.test_ascend_x1_runtime import runtime as runtime, wake, result
from tests.test_x1_workspace_mapping import approval


def section_diagnostic(**changes):
    return dict(schema_version=1, selected_candidate_count=0, recognized_section_labels=["Load Basics", "Customer Info"],
        approved_state_markers=[], target_relationship_kinds=[], visible_target_count=0, heading_root_count=0,
        unique_candidate_count=0, failed_predicate="UNIQUE_CANDIDATE_COUNT_ZERO", **changes)


@pytest.mark.parametrize("key,value", [
    ("recognized_section_labels", ["PRIVATE_CUSTOMER"]), ("approved_state_markers", ["PRIVATE_CLASS"]),
    ("target_relationship_kinds", ["PRIVATE_HREF"]), ("failed_predicate", "PRIVATE_ERROR"),
    ("raw_html", "PRIVATE_HTML"), ("visible_target_count", -1), ("selected_candidate_count", 1000001),
    ("recognized_section_labels", ["Load Basics", "Load Basics"]),
])
def test_section_diagnostic_rejects_private_or_unbounded_metadata(key, value):
    body = section_diagnostic()
    body[key] = value
    with pytest.raises(ValidationError):
        MappingSectionDiagnostic.model_validate(body)


def test_section_failure_keeps_last_completed_identity_stage():
    last = MappingDiagnostic(stage="WORKSPACE_IDENTITY_VERIFIED", candidate_workspace_count=1,
        identity_signal_count=2, section_control_count=12, elapsed_ms=9, section_diagnostic=section_diagnostic())
    assert last.stage == "WORKSPACE_IDENTITY_VERIFIED"
    assert last.section_diagnostic.failed_predicate == "UNIQUE_CANDIDATE_COUNT_ZERO"
    assert "PRIVATE" not in last.model_dump_json()


def test_precise_section_diagnostics_from_synthetic_dom(tmp_path):
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel="msedge", headless=True,
                env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)})
            context = await browser.new_context(service_workers="block")
            await context.route("**/*", lambda request: request.fulfill(content_type="text/html", body="<title>Offline section fixture</title>"))
            page = await context.new_page()
            try:
                await page.goto("https://ascendtms.com/loads")
                for file in ["contract.js", "read-errors.js", "load-board-view.js", "detail-scope.js", "webbridge.js", "mapping-scope.js", "workspace.js", "reader.js"]:
                    await page.add_script_tag(path=str(EXT / file))
                nav = '<nav>'+''.join('<a href="#">'+name+'</a>' for name in ["Dashboard", "Loads", "Customers", "Carriers"] )+'</nav>'
                def html(controls, panels):
                    return nav + '<main><h1>Load #900001</h1><nav><button>Load Basics</button><button>Customer Info</button></nav>'+controls+panels+'</main>'
                async def inspect(controls='', panels=''):
                    await page.evaluate("body=>document.body.innerHTML=body", html(controls, panels))
                    output = await page.evaluate("""()=>{try{
                      const workspace=FreightDeskWorkspace.observeWorkspace(document,null,1), section=FreightDeskWorkspace.observeSection(workspace);
                      return {name:section.name,diagnostic:section.diagnostic};
                    }catch(error){return {code:error.message,diagnostic:error.section_diagnostic};}}""")
                    MappingSectionDiagnostic.model_validate(output["diagnostic"])
                    assert "PRIVATE" not in json.dumps(output)
                    return output

                zero = await inspect()
                assert zero["code"] == "WORKSPACE_SECTION_UNVERIFIED"
                assert zero["diagnostic"]["selected_candidate_count"] == 0
                assert zero["diagnostic"]["unique_candidate_count"] == 0
                assert zero["diagnostic"]["failed_predicate"] == "UNIQUE_CANDIDATE_COUNT_ZERO"
                assert zero["diagnostic"]["recognized_section_labels"] == ["Customer Info", "Load Basics"]
                structure = zero["diagnostic"]["structure_diagnostic"]
                assert structure["observation_scope"] == "VERIFIED_WORKSPACE_ONLY"
                assert structure["status"] == "CAPTURED"
                assert structure["selected_controls"] == []
                assert structure["heading_candidate_count"] == 1
                assert structure["heading_candidates"][0]["section_label"] == "UNCLASSIFIED"
                assert structure["workspace_direct_child_count"] == 2

                # Reproduce the observed category of failure without asserting any live selector:
                # four active controls, no recognized target relationships, no supported heading root.
                gap = await inspect('<div><a class="active" onclick="PRIVATE_SCRIPT()" href="#">Load Basics</a>'
                    '<button class="active">PRIVATE_A</button><button class="active">PRIVATE_B</button><button class="active">PRIVATE_C</button></div>',
                    '<div><div>Load Basics</div><input value="PRIVATE_FIELD_VALUE"></div>')
                assert gap["code"] == "WORKSPACE_SECTION_UNVERIFIED"
                assert gap["diagnostic"]["selected_candidate_count"] == 4
                assert gap["diagnostic"]["target_relationship_kinds"] == []
                assert gap["diagnostic"]["unique_candidate_count"] == 0
                structure = gap["diagnostic"]["structure_diagnostic"]
                selected = structure["selected_controls"][0]
                assert selected["section_label"] == "Load Basics"
                assert selected["onclick_present"] is True
                assert selected["references"] == [{"attribute": "HREF", "shape": "EMPTY_FRAGMENT"}]
                assert selected["parent_tag"] == "div" and selected["workspace_child_index"] == 2
                assert selected["anchor_destination"] == dict(same_origin=True, same_path=True, fragment_present=True, query_present=False)
                assert structure["workspace_direct_children"][-1]["descendant_field_control_count"] == 1
                assert structure["workspace_direct_children"][-1]["tag"] == "div"
                assert structure["workspace_direct_children"][-1]["immediate_heading_labels"] == []
                assert all(item["section_label"] == "UNCLASSIFIED" for item in structure["selected_controls"][1:])

                for href, expected in [('/loads?PRIVATE_QUERY=PRIVATE_VALUE#PRIVATE_FRAGMENT', dict(same_origin=True, same_path=True, fragment_present=True, query_present=True)),
                    ('https://example.invalid/PRIVATE_PATH', dict(same_origin=False, same_path=False, fragment_present=False, query_present=False))]:
                    observed = await inspect('<a class="active" href="'+href+'">Load Basics</a>')
                    assert observed["diagnostic"]["structure_diagnostic"]["selected_controls"][0]["anchor_destination"] == expected
                script = await inspect('<a class="active" href="javascript:PRIVATE_SCRIPT(123)">Load Basics</a>')
                assert script["diagnostic"]["structure_diagnostic"]["selected_controls"][0]["references"] == [{"attribute": "HREF", "shape": "SCRIPT_REFERENCE"}]
                assert script["diagnostic"]["structure_diagnostic"]["selected_controls"][0]["anchor_destination"] is None

                unsupported_root = await inspect(panels='<div><h2>Load Basics</h2></div>')
                assert unsupported_root["diagnostic"]["unique_candidate_count"] == 0
                heading_detail = unsupported_root["diagnostic"]["structure_diagnostic"]["heading_candidates"][1]
                assert heading_detail["section_label"] == "Load Basics"
                assert heading_detail["root_kind"] == "NONE" and heading_detail["predicate"] == "NO_SUPPORTED_ROOT"

                states = [('aria-selected="true"', "ARIA_SELECTED_TRUE"), ('aria-current="page"', "ARIA_CURRENT_PAGE"),
                    ('aria-current="true"', "ARIA_CURRENT_TRUE"), ('class="active PRIVATE_CLASS"', "CLASS_ACTIVE")]
                for attributes, marker in states:
                    selected = await inspect('<button '+attributes+' aria-controls="PRIVATE_TARGET">Load Basics</button>',
                        '<section id="PRIVATE_TARGET"><input value="PRIVATE_VALUE"></section>')
                    assert selected["name"] == "Load Basics"
                    assert selected["diagnostic"]["selected_candidate_count"] == 1
                    assert selected["diagnostic"]["approved_state_markers"] == [marker]
                    assert selected["diagnostic"]["target_relationship_kinds"] == ["ARIA_CONTROLS"]
                    assert selected["diagnostic"]["visible_target_count"] == 1
                    assert selected["diagnostic"]["unique_candidate_count"] == 1
                    assert selected["diagnostic"]["failed_predicate"] is None
                parent = await inspect('<div class="active"><button href="#PRIVATE_TARGET">Load Basics</button></div>', '<section id="PRIVATE_TARGET"></section>')
                assert parent["diagnostic"]["approved_state_markers"] == ["PARENT_CLASS_ACTIVE"]
                assert parent["diagnostic"]["target_relationship_kinds"] == ["FRAGMENT"]

                for attribute, kind in [('data-target', 'DATA_TARGET'), ('data-bs-target', 'DATA_BS_TARGET')]:
                    target = await inspect('<button class="active" '+attribute+'="#PRIVATE_TARGET">Load Basics</button>', '<section id="PRIVATE_TARGET"></section>')
                    assert target["diagnostic"]["target_relationship_kinds"] == [kind]
                labelled = await inspect('<button id="PRIVATE_TAB" class="active">Load Basics</button>', '<section role="tabpanel" aria-labelledby="PRIVATE_TAB"></section>')
                assert labelled["diagnostic"]["target_relationship_kinds"] == ["LABELLEDBY"]

                hidden = await inspect('<button class="active" aria-controls="PRIVATE_TARGET">Load Basics</button>', '<section id="PRIVATE_TARGET" hidden><h2>Load Basics</h2></section>')
                assert hidden["diagnostic"]["selected_candidate_count"] == 1
                assert hidden["diagnostic"]["visible_target_count"] == 0
                assert hidden["diagnostic"]["heading_root_count"] == 0
                assert hidden["diagnostic"]["failed_predicate"] == "UNIQUE_CANDIDATE_COUNT_ZERO"
                missing = await inspect('<button class="active" aria-controls="PRIVATE_MISSING">Load Basics</button>')
                assert missing["diagnostic"]["target_relationship_kinds"] == ["ARIA_CONTROLS"]
                assert missing["diagnostic"]["visible_target_count"] == 0

                heading = await inspect(panels='<section><h2>Load Basics</h2></section>')
                assert heading["diagnostic"]["heading_root_count"] == 1
                assert heading["diagnostic"]["selected_candidate_count"] == 0
                assert heading["name"] == "Load Basics"
                ambiguous = await inspect(panels='<section><h2>Load Basics</h2></section><section><h2>Customer Info</h2></section>')
                assert ambiguous["diagnostic"]["heading_root_count"] == 2
                assert ambiguous["diagnostic"]["unique_candidate_count"] == 2
                assert ambiguous["diagnostic"]["failed_predicate"] == "UNIQUE_CANDIDATE_COUNT_MULTIPLE"
                duplicate = await inspect('<button class="active" aria-controls="PRIVATE_TARGET">Load Basics</button><button class="active" href="#PRIVATE_TARGET">Load Basics</button>', '<section id="PRIVATE_TARGET"></section>')
                assert duplicate["diagnostic"]["selected_candidate_count"] == 2
                assert duplicate["diagnostic"]["visible_target_count"] == 1
                assert duplicate["diagnostic"]["unique_candidate_count"] == 1
                unclassified = await inspect('<button class="active" aria-controls="PRIVATE_TARGET">PRIVATE_LABEL</button>', '<section id="PRIVATE_TARGET"></section>')
                assert "UNCLASSIFIED" in unclassified["diagnostic"]["recognized_section_labels"]

                bound = await inspect('<button class="active">Load Basics</button>'*25)
                assert bound["code"] == "WORKSPACE_BOUND"
                assert bound["diagnostic"]["selected_candidate_count"] == 25
                assert bound["diagnostic"]["failed_predicate"] == "SELECTED_CANDIDATE_BOUND"
                assert bound["diagnostic"]["structure_diagnostic"]["status"] == "PARTIAL"
                assert bound["diagnostic"]["structure_diagnostic"]["selected_controls"] == []
                assert {"category": "SELECTED_CONTROLS", "measured": 25, "maximum": 24} in bound["diagnostic"]["structure_diagnostic"]["diagnostic_bounds"]
                heading_bound = await inspect(panels='<section>'+'<h2>Load Basics</h2>'*48+'</section>')
                assert heading_bound["diagnostic"]["failed_predicate"] == "HEADING_CANDIDATE_BOUND"
                assert heading_bound["diagnostic"]["structure_diagnostic"]["heading_candidates"] == []
                assert {"category": "HEADING_CANDIDATES", "measured": 49, "maximum": 48} in heading_bound["diagnostic"]["structure_diagnostic"]["diagnostic_bounds"]
                layout_bound = await inspect(panels='<div><input value="PRIVATE"></div>'*23)
                assert layout_bound["diagnostic"]["failed_predicate"] == "UNIQUE_CANDIDATE_COUNT_ZERO"
                assert layout_bound["diagnostic"]["structure_diagnostic"]["workspace_direct_children"] == []
                assert layout_bound["diagnostic"]["structure_diagnostic"]["diagnostic_bounds"] == [{"category": "WORKSPACE_DIRECT_CHILDREN", "measured": 25, "maximum": 24}]

                # Expected section is never passed to the resolver and cannot manufacture proof.
                await page.evaluate("body=>document.body.innerHTML=body", html('', ''))
                result = await page.evaluate("""async()=>{const reader=await FreightDeskX1Reader.create(document,location.origin), stages=[];
                  const command={version:1,request_id:'a'.repeat(32),operation:'ASCEND_MAP_WORKSPACE',load_id:null,expected_revision:null,tenant_id:'booking-logistics',actor:'FreightDesk/Avery',approved_load_ids:['900001'],owner_present:false,lease_expires_at:Date.now()/1000+60,capture_load_id:'900001',capture_section:'Load Basics'};
                  try{await reader.executeRuntime(command,()=>{},d=>stages.push(d));return {unexpected:true};}
                  catch(error){return {code:error.message,stages,diagnostic:reader.mappingSectionDiagnostic()};}}""")
                assert result["code"] == "WORKSPACE_SECTION_UNVERIFIED"
                assert result["stages"][-1]["stage"] == "WORKSPACE_IDENTITY_VERIFIED"
                assert result["diagnostic"]["failed_predicate"] == "UNIQUE_CANDIDATE_COUNT_ZERO"
                assert "PRIVATE" not in json.dumps(result)
            finally:
                await context.close()
                await browser.close()
    asyncio.run(run())


@pytest.mark.parametrize("bad_metadata", [False, True])
def test_host_section_failure_persists_only_typed_metadata_and_last_completed_stage(runtime, bad_metadata):
    access, controller, *_ = runtime
    access.enable(mapping=approval(), owner_authorized=True)
    access.request_mapping_capture(owner_authorized=True)
    dispatch = wake(controller)
    controller.finish(result(dispatch, session()))
    dispatch = wake(controller)
    assert dispatch["command"]["operation"] == "ASCEND_MAP_WORKSPACE"
    for elapsed, stage in enumerate(["SESSION_VERIFIED", "ENTITY_DISCOVERY", "LOAD_WORKSPACE_CANDIDATE_FOUND", "WORKSPACE_IDENTITY_VERIFIED"], 1):
        controller.mapping_progress(dict(kind="RUNTIME_MAPPING_PROGRESS", request_id=uuid4().hex,
            command_request_id=dispatch["command"]["request_id"], route=dispatch["route"],
            diagnostic=dict(stage=stage, candidate_workspace_count=1, identity_signal_count=2,
                section_control_count=12, elapsed_ms=elapsed)))
    evidence = section_diagnostic()
    if bad_metadata:
        evidence["recognized_section_labels"] = ["PRIVATE_CUSTOMER_LABEL"]
    stopped = controller.finish(result(dispatch, {"section_diagnostic": evidence, "raw_html": "PRIVATE_HTML"}, "WORKSPACE_SECTION_UNVERIFIED"))
    assert stopped["status"]["error_code"] == "WORKSPACE_SECTION_UNVERIFIED"
    assert stopped["status"]["mapping_diagnostic"]["stage"] == "WORKSPACE_IDENTITY_VERIFIED"
    with access.database(readonly=True) as db:
        bodies = [row[0] for row in db.execute("SELECT body FROM runtime_mapping_diagnostics ORDER BY id")]
        assert "PRIVATE" not in "".join(bodies)
        final = json.loads(bodies[-1])
        assert final["stop_code"] == "WORKSPACE_SECTION_UNVERIFIED"
        assert final["diagnostic"]["stage"] == "WORKSPACE_IDENTITY_VERIFIED"
        assert db.execute("SELECT COUNT(*) FROM runtime_provider_maps").fetchone()[0] == 0
        if bad_metadata:
            assert final["diagnostic"].get("section_diagnostic") is None
        else:
            assert final["diagnostic"]["section_diagnostic"]["failed_predicate"] == "UNIQUE_CANDIDATE_COUNT_ZERO"
        assert final["production_writes"] is False
