"""Offline document/build and retained-evidence regression checks."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from executors.ascend_extension.bridge_build import BUILD, DocumentHandshake
from executors.ascend_extension.runtime_contracts import RuntimeWake
from tests.test_ascend_x1_controller import repo as repo, route
from tests.test_ascend_x1_runtime import runtime as runtime, cycle, wake


def proof():
    return {**BUILD, "service_worker_version": BUILD["extension_version"],
            "content_script_version": BUILD["extension_version"], "document_generation": 1,
            "tab_id": route()["tab_id"], "document_id": route()["document_id"]}


@pytest.mark.parametrize("key,value", [("content_script_version", "0.4.0"), ("service_worker_version", "0.3.1"),
                                      ("controller_revision", 1), ("native_protocol", 2),
                                      ("content_protocol", 1), ("document_generation", 0), ("native_protocol", True)])
def test_handshake_mismatch_rejected(key, value):
    with pytest.raises(ValidationError):
        DocumentHandshake.model_validate({**proof(), key: value})


def test_document_id_cannot_reuse_other_route():
    with pytest.raises(ValidationError):
        RuntimeWake(kind="RUNTIME_WAKE", request_id="a" * 32, build=BUILD,
                    route=route(), handshake={**proof(), "document_id": "e" * 32})


def test_handshake_retained_without_enrollment_mutation(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    response = controller.wake(dict(kind="RUNTIME_WAKE", request_id="a" * 32, build=BUILD, handshake=proof(), route=route()))
    assert response["kind"] == "RUNTIME_DISPATCH"
    assert access.status()["document_handshake"] == proof()


@pytest.mark.parametrize("state,code", [("CONTENT_SCRIPT_STALE", "CONTENT_SCRIPT_MISSING"),
                                       ("CONTENT_SCRIPT_STALE", "CONTENT_SCRIPT_OLD_VERSION"),
                                       ("CONTENT_SCRIPT_STALE", "CONTENT_SCRIPT_PORT_STALE"),
                                       ("TAB_DISCOVERY_FAILED", "DOCUMENT_CHANGED"),
                                       ("CONTENT_SCRIPT_STALE", "CONTENT_SCRIPT_INJECTION_BLOCKED")])
def test_invalidated_proof_marks_board_retained(runtime, state, code):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    current = cycle(controller)["status"]
    assert current["board_evidence_status"] == "CURRENT_VERIFIED_BOARD"
    stopped = controller.wake(dict(kind="RUNTIME_WAKE", request_id="a" * 32, route=None,
                                  routing_state=state, routing_error=code, eligible_tab_count=1))["status"]
    assert stopped["error_code"] == code
    assert stopped["board_evidence_status"] == "LAST_KNOWN_BOARD_EVIDENCE"
    assert stopped["load_count"] == current["load_count"]
    assert stopped["board_hash"] == current["board_hash"]
    assert stopped["read_access"] == "ENABLED"
    assert stopped["bound_tab"] == "UNBOUND"


def test_revoke_keeps_only_last_known_board(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    access.disable(owner_authorized=True)
    assert access.status()["board_evidence_status"] == "LAST_KNOWN_BOARD_EVIDENCE"
    assert "command" not in wake(controller)


def test_packaged_build_and_host_scope():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "extensions/ascend-x1/manifest.json").read_text())
    assert manifest["version"] == BUILD["extension_version"]
    assert manifest["host_permissions"] == ["https://ascendtms.com/*"]
    assert set(manifest["permissions"]) == {"scripting", "nativeMessaging", "storage", "alarms"}
    router = (root / "extensions/ascend-x1/tab-router.js").read_text()
    assert "tabs.reload" not in router
    assert "world:'ISOLATED'" in router and "frameIds:[0]" in router
    assert "func:" not in router
