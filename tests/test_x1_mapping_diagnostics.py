"""Offline stage receipts, privacy and timeout tests."""
import json
from uuid import uuid4
import pytest
from pydantic import ValidationError
from executors.ascend_extension.mapping_diagnostics import MappingDiagnostic, STAGES
from executors.ascend_extension.mapping_store import report_maps
from tests.test_ascend_x1_controller import repo as repo, session
from tests.test_ascend_x1_runtime import runtime as runtime, wake, result
from tests.test_x1_workspace_mapping import approval, provider_map


def dispatch_mapping(access, controller):
    access.enable(mapping=approval(), owner_authorized=True)
    access.request_mapping_capture(owner_authorized=True)
    d = wake(controller)
    controller.finish(result(d, session()))
    return wake(controller)


def progress(controller, d, stage, elapsed=1):
    return controller.mapping_progress(dict(kind="RUNTIME_MAPPING_PROGRESS", request_id=uuid4().hex,
        command_request_id=d["command"]["request_id"], route=d["route"], diagnostic=dict(stage=stage,
        candidate_workspace_count=1, identity_signal_count=2, section_control_count=2, elapsed_ms=elapsed)))


@pytest.mark.parametrize("stage", STAGES[1:-1])
def test_timeout_preserves_last_completed_stage(runtime, stage):
    access, controller, now, *_ = runtime
    d = dispatch_mapping(access, controller)
    for s in STAGES[1:STAGES.index(stage)+1]:
        assert progress(controller, d, s)["kind"] == "RUNTIME_MAPPING_PROGRESS_ACK"
    now[0] += 13
    stopped = wake(controller)["status"]
    assert stopped["error_code"] == "READ_TIMEOUT"
    assert stopped["mapping_diagnostic"]["stage"] == stage
    report = report_maps(access, approval().session_id)
    assert report["captures"] == 0
    assert report["capture_diagnostics"][-1]["stop_code"] == "READ_TIMEOUT"


def test_persistence_stage_host_only_and_no_raw_fields(runtime):
    access, controller, *_ = runtime
    d = dispatch_mapping(access, controller)
    with pytest.raises(PermissionError):
        progress(controller, d, "MAP_PERSISTED")
    for s in STAGES[1:-1]:
        progress(controller, d, s)
    response = controller.finish(result(d, provider_map()))
    assert response["status"]["mapping_diagnostic"]["stage"] == "MAP_PERSISTED"
    report = report_maps(access, approval().session_id)
    assert report["captures"] == 1 and report["capture_diagnostics"][-1]["stop_code"] is None
    assert report["values_included"] is False and report["production_writes"] is False
    with pytest.raises(ValidationError):
        MappingDiagnostic(stage="ENTITY_DISCOVERY",candidate_workspace_count=0,identity_signal_count=0,section_control_count=0,elapsed_ms=0,raw="PRIVATE")
    with access.database() as db:
        with pytest.raises(Exception, match="append_only"):
            db.execute("DELETE FROM runtime_mapping_diagnostics")
    assert "PRIVATE" not in json.dumps(report)


def test_nonload_safe_failure_and_revoke_reject_progress(runtime):
    access, controller, *_ = runtime
    d = dispatch_mapping(access, controller)
    progress(controller, d, "SESSION_VERIFIED")
    progress(controller, d, "ENTITY_DISCOVERY")
    status = controller.finish(result(d, None, "NOT_A_LOAD_WORKSPACE"))["status"]
    assert status["error_code"] == "NOT_A_LOAD_WORKSPACE"
    assert status["mapping_diagnostic"]["stage"] == "ENTITY_DISCOVERY"
    access.disable(owner_authorized=True)
    with pytest.raises(PermissionError):
        progress(controller, d, "LOAD_WORKSPACE_CANDIDATE_FOUND")


def test_target_persistence_scope_and_progress_sequence(runtime):
    access, controller, *_ = runtime
    a = approval(capture_load_id="1755", capture_section="Load Basics", max_captures=1)
    access.enable(mapping=a, owner_authorized=True)
    access.request_mapping_capture(owner_authorized=True)
    d = wake(controller)
    controller.finish(result(d, session()))
    d = wake(controller)
    assert d["command"]["capture_load_id"] == "1755"
    progress(controller, d, "SESSION_VERIFIED")
    with pytest.raises(PermissionError):
        progress(controller, d, "SESSION_VERIFIED")
    status = controller.finish(result(d, provider_map(section="Customer Info")))["status"]
    assert status["error_code"] == "WORKSPACE_SCOPE_DENIED"
    assert report_maps(access, a.session_id)["captures"] == 0
