"""Persistent-runtime unit fixtures only; no browser, vendor or real enrollment execution."""

import hashlib
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from executors.ascend_extension.native import canonical
from executors.ascend_extension.runtime import RuntimeAccess, RuntimeController
from executors.ascend_extension.runtime_contracts import RuntimeCommand, RuntimeWake
from tests.test_ascend_x1_controller import repo as repo, route, session, view_contract


@pytest.fixture
def runtime(repo):
    now = [1000.0]
    enrollment = {"generation": "e" * 32, "installation_id": repo.config()["installation_id"]}
    kwargs = {"clock": lambda: now[0], "enrollment_guard": lambda: enrollment, "gate": lambda _: None}
    access = RuntimeAccess(repo, **kwargs)
    controller = RuntimeController(repo, **kwargs)
    return access, controller, now, enrollment, kwargs


def wake(controller, tab=None, **values):
    return controller.wake(
        {
            "kind": "RUNTIME_WAKE",
            "request_id": uuid4().hex,
            "route": route() if tab is None else tab,
            "owner_present": True,  # Synthetic private-content readiness; no live owner proof.
            **values,
        }
    )


def result(dispatch, evidence, error=None):
    return {
        "kind": "RUNTIME_RESULT",
        "request_id": uuid4().hex,
        "command_request_id": dispatch["command"]["request_id"],
        "route": dispatch["route"],
        "evidence": evidence,
        "error_code": error,
    }


def board(ids=("42", "91")):
    rows = [{"load_id": i, "pick_date": None, "drop_date": None} for i in ids]
    rows.sort(key=lambda r: int(r["load_id"]))
    return {
        "source_view": "ACTIVE_LOADS",
        "coverage": "VISIBLE_BOARD_ONLY",
        "rows": rows,
        "board_hash": hashlib.sha256(canonical(rows)).hexdigest(),
        "view_contract": view_contract(),
    }


def cycle(controller, rows=None):
    for op, evidence in [
        ("ASCEND_GET_SESSION_STATE", session()),
        ("ASCEND_NAVIGATE_ACTIVE_LOADS", {"view_contract": view_contract()}),
        ("ASCEND_GET_ACTIVE_LOADS", board() if rows is None else rows),
    ]:
        dispatch = wake(controller)
        assert dispatch["command"]["operation"] == op
        response = controller.finish(result(dispatch, evidence))
    return response


def test_disabled_status_neither_creates_state_nor_loads_enrollment(runtime):
    access, controller, *_ = runtime
    access.enrollment_guard = lambda: pytest.fail("No DPAPI read for status")
    assert access.status()["read_access"] == "DISABLED"
    assert access.status()["load_count"] is None
    assert not access.path.exists()
    assert wake(controller)["status"]["read_access"] == "DISABLED"
    with access.database(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM runtime_leases").fetchone()[0] == 0


def test_enrolled_channel_visible_before_first_read_lease(runtime):
    access, controller, *_ = runtime
    status = controller.status()["status"]
    assert status["state"] == "PAIRED"
    assert status["pairing"] == "VALID"
    assert status["read_access"] == "DISABLED"
    assert access.status()["pairing"] == "VALID"


def test_enabling_lease_does_not_resume_paused_runtime(runtime):
    access, *_ = runtime
    access.set_paused(True, owner_authorized=True)
    assert access.enable(owner_authorized=True)["state"] == "PAUSED"
    access.set_paused(False, owner_authorized=True)
    assert access.check()["writes"] == "FORBIDDEN"


def test_security_invalidation_clears_pairing_status(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    controller.status()
    controller.invalidate("SECURITY_MISMATCH")
    assert access.status()["pairing"] == "UNKNOWN"


def test_other_sanitized_same_origin_view_only_dispatches_session_first(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    assert wake(controller, route("OTHER"))["command"]["operation"] == "ASCEND_GET_SESSION_STATE"


def test_trusted_workflow_detail_uses_lease_without_new_owner_grant(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    access.request_detail_for_workflow("42")
    cycle(controller)
    assert wake(controller)["command"]["operation"] == "ASCEND_FIND_LOAD"


def test_owner_enable_eight_hour_lease_and_restart(runtime, repo):
    access, _, now, _, kwargs = runtime
    with pytest.raises(PermissionError, match="OWNER_REQUIRED"):
        access.enable()
    assert access.enable(owner_authorized=True)["lease_expires_at"] == 29800
    restarted = RuntimeAccess(repo, **kwargs)
    assert restarted.check()["writes"] == "FORBIDDEN"
    now[0] = 29800
    assert restarted.status()["read_access"] == "EXPIRED"
    with pytest.raises(PermissionError, match="READ_LEASE_EXPIRED"):
        restarted.check()


@pytest.mark.parametrize("hours,interval", [(0, 300), (25, 300), (True, 300), (8, 1), (8, True)])
def test_invalid_lease_config_does_not_create(runtime, hours, interval):
    access, *_ = runtime
    with pytest.raises(ValueError):
        access.enable(owner_authorized=True, hours=hours, interval_seconds=interval)
    assert not access.path.exists()


def test_revoke_persists_across_process_and_rejects_inflight(runtime, repo):
    access, controller, _, _, kwargs = runtime
    access.enable(owner_authorized=True)
    dispatch = wake(controller)
    access.disable(owner_authorized=True)
    with pytest.raises(PermissionError, match="READ_LEASE_REVOKED"):
        controller.finish(result(dispatch, session()))
    assert RuntimeAccess(repo, **kwargs).status()["read_access"] == "REVOKED"


def test_pairing_generation_mismatch_revokes_lease(runtime):
    access, controller, _, enrollment, _ = runtime
    access.enable(owner_authorized=True)
    dispatch = wake(controller)
    enrollment["generation"] = "a" * 32
    with pytest.raises(PermissionError, match="SECURITY_MISMATCH"):
        controller.finish(result(dispatch, session()))
    assert access.status()["read_access"] == "REVOKED"


def test_owner_pause_and_rebind_invalidate_inflight(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    dispatch = wake(controller)
    access.set_paused(True, owner_authorized=True)
    with pytest.raises(PermissionError, match="RUNTIME_PAUSED"):
        controller.finish(result(dispatch, session()))
    access.set_paused(False, owner_authorized=True)
    before = access.status()["control_revision"]
    access.request_rebind(owner_authorized=True)
    assert access.status()["control_revision"] == before + 1
    assert access.status()["bound_tab"] == "UNBOUND"


def test_policy_gate_checked_dispatch_and_receipt(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    dispatch = wake(controller)

    def blocked(_):
        raise PermissionError("READ_POLICY_BLOCKED")

    controller.access.gate = blocked
    with pytest.raises(PermissionError, match="READ_POLICY_BLOCKED"):
        controller.finish(result(dispatch, session()))
    assert wake(controller)["status"]["error_code"] == "READ_POLICY_BLOCKED"


@pytest.mark.parametrize(
    "operation",
    ["SAVE", "SUBMIT", "SET_DRIVER", "UPDATE_STATUS", "ADD_NOTE", "UPLOAD_DOCUMENT", "ASCEND_WRITE_LOAD"],
)
def test_write_commands_not_representable(operation):
    with pytest.raises(ValidationError):
        RuntimeCommand(request_id=uuid4().hex, operation=operation)


def test_page_cannot_schedule_operations_or_selectors():
    with pytest.raises(ValidationError):
        RuntimeWake(kind="RUNTIME_WAKE", request_id=uuid4().hex, operation="ASCEND_OPEN_LOAD_READONLY")
    with pytest.raises(ValidationError):
        RuntimeCommand(request_id=uuid4().hex, operation="ASCEND_GET_ACTIVE_LOADS", selector="input")


def test_host_owned_cycle_hash_noop_and_change_without_fixed_oracle(runtime, repo):
    access, controller, now, _, kwargs = runtime
    access.enable(owner_authorized=True)
    response = cycle(controller)
    assert response["status"]["load_count"] == 2
    assert response["status"]["last_board_sync"] == now[0]
    assert "command" not in wake(controller)
    now[0] += 301
    cycle(RuntimeController(repo, **kwargs))
    now[0] += 301
    cycle(controller, board(("500",)))
    with access.database(readonly=True) as db:
        proposals = [json.loads(x[0]) for x in db.execute("SELECT body FROM runtime_proposals")]
        events = [json.loads(x[0]) for x in db.execute("SELECT body FROM runtime_events")]
    assert len(proposals) == 2
    assert all(p["coverage"] == "VISIBLE_BOARD_ONLY" and p["canonical_mutation"] is False for p in proposals)
    assert [e["result_code"] for e in events if e["kind"] == "PROPOSAL"] == [
        "BOARD_REFRESHED",
        "BOARD_UNCHANGED",
        "BOARD_REFRESHED",
    ]
    assert all("provider_facts" not in e and "rows" not in e for e in events)


def test_empty_board_supported_only_with_independent_view(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    assert cycle(controller, board(()))["status"]["load_count"] == 0


def test_view_missing_proof_stops_before_manifest(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    controller.finish(result(wake(controller), session()))
    response = controller.finish(result(wake(controller), {"view_contract": view_contract(selected=False)}))
    assert response["status"]["error_code"] == "ACTIVE_VIEW_UNVERIFIED"
    assert wake(controller)["status"]["state"] == "VIEW_UNVERIFIED"
    with access.database(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM runtime_proposals").fetchone()[0] == 0


def test_view_changed_before_board_stops(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    controller.finish(result(wake(controller), session()))
    controller.finish(result(wake(controller), {"view_contract": view_contract()}))
    evidence = board()
    evidence["view_contract"] = view_contract("ALL_LOADS")
    assert controller.finish(result(wake(controller), evidence))["status"]["state"] == "STOPPED"


def test_replay_resistance_survives_host_restart(runtime, repo):
    access, controller, _, _, kwargs = runtime
    access.enable(owner_authorized=True)
    raw = {"kind": "RUNTIME_WAKE", "request_id": uuid4().hex, "route": route()}
    dispatch = controller.wake(raw)
    with pytest.raises(PermissionError, match="DUPLICATE_REQUEST"):
        RuntimeController(repo, **kwargs).wake(raw)
    receipt = result(dispatch, session())
    controller.finish(receipt)
    with pytest.raises(PermissionError, match="DUPLICATE_REQUEST"):
        RuntimeController(repo, **kwargs).finish(receipt)


def test_pending_dispatch_survives_host_restart_without_duplicate(runtime, repo):
    access, controller, now, _, kwargs = runtime
    access.enable(owner_authorized=True)
    pending = wake(controller)
    restarted = RuntimeController(repo, **kwargs)
    assert "command" not in wake(restarted)
    restarted.finish(result(pending, session()))
    assert wake(restarted)["command"]["operation"] == "ASCEND_NAVIGATE_ACTIVE_LOADS"
    now[0] += 16
    assert wake(restarted)["status"]["error_code"] == "READ_TIMEOUT"


def test_logout_then_reauth_resumes_without_new_grant(runtime):
    access, controller, now, *_ = runtime
    access.enable(owner_authorized=True)
    response = controller.finish(result(wake(controller), session(False)))
    assert response["status"]["session"] == "ASCEND_REAUTH_REQUIRED"
    assert response["status"]["action"] == "Sign into Ascend."
    now[0] += 6
    controller.finish(result(wake(controller), session()))
    assert wake(controller)["command"]["operation"] == "ASCEND_NAVIGATE_ACTIVE_LOADS"


def test_route_rebind_always_restarts_session(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    changed = route()
    changed.update(tab_id=9, document_id="9" * 32)
    assert wake(controller, changed)["command"]["operation"] == "ASCEND_GET_SESSION_STATE"


def test_session_probes_bounded_and_do_not_advance_board(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    for _ in range(10):
        dispatch = wake(controller, probe_only=True)
        assert dispatch["command"]["operation"] == "ASCEND_GET_SESSION_STATE"
        controller.finish(result(dispatch, session()))
    with pytest.raises(PermissionError, match="RUNTIME_PROBE_BOUND"):
        wake(controller, probe_only=True)
    assert wake(controller)["command"]["operation"] == "ASCEND_GET_SESSION_STATE"


def test_replacement_lease_rejects_prior_receipt_and_keeps_history(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    pending = wake(controller)
    access.enable(owner_authorized=True)
    with pytest.raises(PermissionError, match="RUNTIME_SEQUENCE_INVALID"):
        controller.finish(result(pending, session()))
    with access.database(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM runtime_leases").fetchone()[0] == 2


def test_lease_expiry_at_receipt_rejects_provider_values(runtime):
    access, controller, now, *_ = runtime
    access.enable(owner_authorized=True, hours=1 / 60)
    pending = wake(controller)
    now[0] += 60
    with pytest.raises(PermissionError, match="READ_LEASE_EXPIRED"):
        controller.finish(result(pending, session()))


def test_safe_audit_does_not_persist_raw_errors(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    controller.finish(result(wake(controller), None, "PRIVATE-COOKIE-CONTACT-NOTE"))
    with access.database(readonly=True) as db:
        text = " ".join(r[0] for r in db.execute("SELECT body FROM runtime_events"))
    assert "PRIVATE" not in text
    assert "READ_EXECUTION_FAILED" in text


def test_only_visible_manifest_ids_can_queue_details(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    with pytest.raises(PermissionError, match="OWNER_REQUIRED"):
        access.queue_detail("42")
    with pytest.raises(PermissionError, match="EXACT_LOAD_MISSING"):
        access.queue_detail("1755", owner_authorized=True)
    access.queue_detail("42", owner_authorized=True)
    cycle(controller)
    dispatch = wake(controller)
    assert dispatch["command"]["operation"] == "ASCEND_FIND_LOAD"
    assert dispatch["command"]["load_id"] == "42"


def test_historical_consumed_grants_remain_untouched(runtime, repo):
    with repo.database() as db:
        db.execute("INSERT INTO consumed VALUES ('x1-read','consumed-historical-fixture')")
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    access.disable(owner_authorized=True)
    with repo.database() as db:
        assert db.execute("SELECT id FROM consumed WHERE kind='x1-read'").fetchall() == [
            ("consumed-historical-fixture",)
        ]


@pytest.mark.parametrize(
    "routing_state,count",
    [("WAITING_FOR_ASCEND", 0), ("TAB_SELECTION_REQUIRED", 2), ("ASCEND_REAUTH_REQUIRED", 1)],
)
def test_routing_lifecycle_invalidates_binding_without_proving_provider_state(runtime, routing_state, count):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    response = controller.wake(
        {
            "kind": "RUNTIME_WAKE",
            "request_id": uuid4().hex,
            "route": None,
            "routing_state": routing_state,
            "eligible_tab_count": count,
        }
    )
    assert response["status"]["state"] == routing_state
    assert response["status"]["view"] == "UNKNOWN"
    assert response["status"]["bound_tab"] == "UNBOUND"
    assert response["binding_hint"] is None


def test_resume_hint_is_not_dashboard_or_authentication_proof(runtime, repo):
    access, controller, now, _, kwargs = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    now[0] += 361
    status = RuntimeController(repo, **kwargs).status()
    assert status["status"]["pairing"] == "VALID"
    assert status["status"]["session"] == "UNKNOWN"
    assert status["binding_hint"] == {"tab_id": 1, "document_id": "f" * 32}
    assert "binding_hint" not in access.status()
    access.disable(owner_authorized=True)
    assert controller.status()["binding_hint"] is None


def test_session_display_freshness_tracks_poll_interval_without_skipping_new_proof(runtime):
    access, controller, now, *_ = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    now[0] += 301
    assert controller.status()["status"]["session"] == "AUTHENTICATED"
    assert wake(controller)["command"]["operation"] == "ASCEND_GET_SESSION_STATE"


def test_detail_chain_requires_identity_and_retains_unknown_contracts(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    access.request_detail_for_workflow("42")
    assert cycle(controller)["status"]["next_due_at"] == 0
    revision = board()["board_hash"]
    controller.finish(
        result(
            wake(controller),
            {"view_contract": view_contract(), "load_id": "42", "exact_row": True, "board_hash": revision},
        )
    )
    identity = {
        "view_contract": view_contract(),
        "expected_load_id": "42",
        "observed_load_id": "42",
        "identity_strategy": "PROVIDER_DETAIL_FIELD",
        "confidence": "VERIFIED",
        "board_hash": revision,
        "row_match": True,
        "opener_belongs_to_row": True,
        "unique_panel": True,
        "detail_field_match": True,
        "direct_panel_reference": False,
        "opener_identity_match": False,
        "selection_transition": False,
        "newly_visible": True,
    }
    controller.finish(result(wake(controller), identity))
    for operation in ("ASCEND_READ_LOAD", "ASCEND_READ_STOPS", "ASCEND_READ_ASSIGNMENT"):
        dispatch = wake(controller)
        assert dispatch["command"]["operation"] == operation
        controller.finish(
            result(
                dispatch,
                {
                    "view_contract": view_contract(),
                    "load_id": "42",
                    "board_hash": revision,
                    "mapping_state": "UNKNOWN",
                    "fields": [],
                },
            )
        )
    with access.database(readonly=True) as db:
        receipts = [json.loads(r[0]) for r in db.execute("SELECT body FROM runtime_receipts")]
    unknown = [
        r
        for r in receipts
        if r["operation"] in ("ASCEND_READ_LOAD", "ASCEND_READ_STOPS", "ASCEND_READ_ASSIGNMENT")
    ]
    assert len(unknown) == 3
    assert all(r["evidence"]["fields"] == [] and r["evidence"]["mapping_state"] == "UNKNOWN" for r in unknown)


def test_protocol_bool_and_unverified_operational_values_rejected():
    from executors.ascend_extension.runtime_contracts import UnknownDetailEvidence

    with pytest.raises(ValidationError):
        RuntimeCommand(version=True, request_id=uuid4().hex, operation="ASCEND_GET_SESSION_STATE")
    with pytest.raises(ValidationError):
        UnknownDetailEvidence(
            view_contract=view_contract(),
            load_id="42",
            board_hash="0" * 64,
            mapping_state="UNKNOWN",
            fields=[{"phone": "PRIVATE"}],
        )


def test_revisited_board_creates_fresh_append_only_provenance(runtime):
    access, controller, now, *_ = runtime
    access.enable(owner_authorized=True)
    cycle(controller)
    now[0] += 301
    cycle(controller, board(("1",)))
    now[0] += 301
    cycle(controller)
    with access.database(readonly=True) as db:
        proposals = [
            json.loads(r[0]) for r in db.execute("SELECT body FROM runtime_proposals ORDER BY rowid")
        ]
    assert len(proposals) == 3
    assert proposals[0]["derived"] == proposals[2]["derived"]
    assert proposals[0]["observed_at"] < proposals[2]["observed_at"]


def test_failed_view_retains_only_validated_safe_candidate_diagnostics(runtime):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    controller.finish(result(wake(controller), session()))
    controller.finish(
        result(wake(controller), {"view_contract": view_contract(selected=False)}, "ACTIVE_VIEW_UNVERIFIED")
    )
    with access.database(readonly=True) as db:
        latest = json.loads(
            db.execute("SELECT body FROM runtime_receipts ORDER BY rowid DESC LIMIT 1").fetchone()[0]
        )
    assert latest["error_code"] == "ACTIVE_VIEW_UNVERIFIED"
    assert latest["evidence"]["view_contract"]["candidate_count"] == 1
    assert latest["evidence"]["view_contract"]["confidence"] == "UNKNOWN"


@pytest.mark.parametrize("private_location", ["extra", "candidate"])
def test_malformed_view_diagnostic_never_persists_private_values(runtime, private_location):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    controller.finish(result(wake(controller), session()))
    raw = {"view_contract": view_contract(selected=False)}
    if private_location == "extra":
        raw["notes"] = "PRIVATE-CUSTOMER-RAW"
    else:
        raw["view_contract"]["candidates"][0]["label"] = "PRIVATE-CUSTOMER-RAW"
    controller.finish(result(wake(controller), raw, "ACTIVE_VIEW_UNVERIFIED"))
    with access.database(readonly=True) as db:
        stored = " ".join(
            row[0]
            for row in db.execute(
                "SELECT body FROM runtime_receipts UNION ALL SELECT body FROM runtime_events"
            )
        )
    assert "PRIVATE-CUSTOMER-RAW" not in stored


def test_scheduler_lease_persists_after_cli_object_exit(runtime):
    access, controller, now, _, kwargs = runtime
    access.enable(owner_authorized=True)
    restarted = RuntimeAccess(access.repo, **kwargs)
    assert restarted.status()["read_access"] == "ENABLED"
    now[0] += 151
    assert restarted.status()["state"] == "SCHEDULER_NOT_RUNNING"
    wake(controller, tab=None)
    assert restarted.status()["scheduler"] == "RUNNING"


def test_bound_before_view_timeout_persists_safe_stage(runtime):
    access, controller, _, _, kwargs = runtime
    access.enable(owner_authorized=True)
    proved = controller.finish(result(wake(controller), session()))
    assert proved["status"]["state"] == "BOUND"
    dispatch = wake(controller)
    failed = controller.finish(result(dispatch, None, "READ_TIMEOUT"))
    assert failed["status"]["state"] == "VIEW_UNVERIFIED"
    stored = RuntimeAccess(access.repo, **kwargs).status()
    assert stored["execution_stage"] == "ASCEND_NAVIGATE_ACTIVE_LOADS"
    assert stored["error_code"] == "READ_TIMEOUT"
    assert stored["last_board_sync"] is None
    assert "command" not in wake(controller)


@pytest.mark.parametrize("state,code", [("CONTENT_SCRIPT_STALE", "REFRESH_ASCEND_TAB"), ("TAB_DISCOVERY_FAILED", "TAB_DISCOVERY_FAILED")])
def test_discovery_failures_do_not_claim_zero_tabs(runtime, state, code):
    access, controller, *_ = runtime
    access.enable(owner_authorized=True)
    response = controller.wake(dict(kind="RUNTIME_WAKE", request_id=uuid4().hex, route=None,
                                    routing_state=state, eligible_tab_count=1))
    assert response["status"]["state"] == state
    assert response["status"]["error_code"] == code
    assert response["status"]["eligible_tab_count"] == 1
