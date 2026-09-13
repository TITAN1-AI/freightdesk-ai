import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from app.core.config import Settings
from app.models.domain import (
    ActionPolicy, AuthorizedIdentity, ExternalEvent, Role, Status, Task, utcnow,
)
from app.services.control_plane import ControlPlane
from app.services.store import Store


def event(plane, **kwargs):
    return ExternalEvent(tenant_id=plane.tenant, shipment_id="DEMO-1847", source="dashboard",
                         kind="REVIEW", **kwargs)


def test_event_idempotency_and_changed_payload(plane, owner):
    e = event(plane)
    assert not plane.process_event(owner, e)["duplicate"]
    assert plane.process_event(owner, e)["duplicate"]
    assert plane.shipment(e.shipment_id).version == 1
    changed = e.model_copy(update={"shipment_id": "DEMO-1848"})
    with pytest.raises(ValueError, match="different content"):
        plane.process_event(owner, changed)


def test_concurrent_duplicate_event_processed_once(plane, owner):
    e = event(plane)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: plane.process_event(owner, e), range(8)))
    assert sum(not r["duplicate"] for r in results) == 1


def test_invalid_transition_rolls_back_receipt_and_state(plane, owner):
    e = event(plane).model_copy(update={"kind": "TRANSITION", "target_status": Status.BILLING_READY,
                                       "expected_version": 0})
    before = len(plane.store.timeline(plane.tenant))
    with pytest.raises(ValueError, match="Invalid transition"):
        plane.process_event(owner, e)
    assert plane.shipment(e.shipment_id).version == 0
    assert len(plane.store.timeline(plane.tenant)) == before
    assert plane.store.db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0


def test_expected_version_blocks_stale_write(plane, owner):
    e = event(plane, expected_version=10)
    with pytest.raises(ValueError, match="version changed"):
        plane.process_event(owner, e)


def test_pause_and_takeover_block_work(plane, owner):
    plane.set_pause(owner, True, "DEMO-1847", takeover=True)
    with pytest.raises(ValueError, match="paused"):
        plane.process_event(owner, event(plane))
    plane.set_pause(owner, False, "DEMO-1847")
    assert not plane.process_event(owner, event(plane))["duplicate"]
    plane.set_pause(owner, True)
    with pytest.raises(ValueError, match="paused"):
        plane.request_action(owner, "DEMO-1847", "routine_customer_update", "paused-request")


def test_allow_executes_without_human_approval(plane, owner):
    plane.update_policy(owner, "routine_customer_update", ActionPolicy.ALLOW)
    result = plane.request_action(owner, "DEMO-1847", "routine_customer_update", "allow-request")
    assert result["status"] == "SIMULATED"
    before = len(plane.store.timeline(plane.tenant))
    assert plane.request_action(owner, "DEMO-1847", "routine_customer_update", "allow-request") == result
    assert len(plane.store.timeline(plane.tenant)) == before
    assert plane.snapshot(owner)["metrics"]["external_actions_completed"] == 0


def test_forbidden_cannot_be_approved_around(plane, owner):
    result = plane.request_action(owner, "DEMO-1847", "routine_customer_update", "approval-request")
    plane.update_policy(owner, "routine_customer_update", ActionPolicy.FORBIDDEN)
    with pytest.raises(PermissionError):
        plane.decide(owner, result["approval_id"], "APPROVED")
    assert plane.policy("unknown_action") == ActionPolicy.FORBIDDEN


def test_stale_approval_expires_without_execution(plane, owner):
    result = plane.request_action(owner, "DEMO-1847", "routine_customer_update", "approval-request")
    plane.process_event(owner, event(plane))
    assert plane.decide(owner, result["approval_id"], "APPROVED")["status"] == "EXPIRED"
    assert not any(a["event"] == "ACTION_SIMULATED" for a in plane.store.timeline(plane.tenant))


def test_approval_can_be_consumed_only_once(plane, owner):
    result = plane.request_action(owner, "DEMO-1847", "routine_customer_update", "approval-request")
    assert plane.decide(owner, result["approval_id"], "APPROVED")["status"] == "APPROVED"
    with pytest.raises(ValueError, match="already decided"):
        plane.decide(owner, result["approval_id"], "APPROVED")


def test_risk_change_expires_approval_even_without_version_change(plane, owner):
    result = plane.request_action(owner, "DEMO-1847", "routine_customer_update", "approval-risk-test")
    with plane.store.transaction():
        shipment = plane.shipment("DEMO-1847")
        shipment.tracking.last_position_at = utcnow() - timedelta(minutes=65)
        plane.save(shipment)
    assert plane.decide(owner, result["approval_id"], "APPROVED")["status"] == "EXPIRED"


def test_today_event_count_is_not_truncated_to_activity_window(plane, owner):
    for _ in range(155):
        plane.process_event(owner, event(plane))
    snapshot = plane.snapshot(owner)
    assert len(snapshot["audit"]) == 150
    assert snapshot["metrics"]["events_processed_today"] == 155


def test_reject_is_audited_without_execution(plane, owner):
    result = plane.request_action(owner, "DEMO-1847", "routine_customer_update", "approval-request")
    plane.decide(owner, result["approval_id"], "REJECTED")
    assert plane.store.timeline(plane.tenant)[0]["event"] == "APPROVAL_REJECTED"


def test_operations_user_cannot_approve(plane):
    actor = AuthorizedIdentity(id="ops", tenant_id=plane.tenant, role=Role.OPERATIONS_USER)
    with pytest.raises(PermissionError):
        plane.decide(actor, "seed-approval", "APPROVED")


def test_append_only_audit_database_guards(plane):
    with pytest.raises(sqlite3.IntegrityError):
        plane.store.db.execute("DELETE FROM audit")
    with pytest.raises(sqlite3.IntegrityError):
        plane.store.db.execute("UPDATE audit SET body='{}'")


def test_restart_preserves_state_and_does_not_reseed(tmp_path, owner):
    path = tmp_path / "restart.sqlite3"
    first = Store(path)
    plane = ControlPlane(first, Settings())
    plane.set_pause(owner, True, "DEMO-1847")
    count = len(first.timeline(plane.tenant))
    first.close()
    second = Store(path)
    restored = ControlPlane(second, Settings())
    assert restored.shipment("DEMO-1847").paused
    assert len(second.timeline(restored.tenant)) == count
    second.close()


def test_storage_tenant_scoping(plane):
    assert plane.store.all("other", "shipment") == []
    with pytest.raises(KeyError):
        plane.store.get("other", "shipment", "DEMO-1847")


def test_scheduler_due_work_and_backoff(plane, monkeypatch):
    with plane.store.transaction():
        task = Task.model_validate(plane.store.all(plane.tenant, "task")[0])
        task.due_at = utcnow() - timedelta(seconds=1)
        plane.store.put(plane.tenant, "task", task.id, task)
    plane.run_due()
    assert any(a["event"] == "TASK_COMPLETED" for a in plane.store.timeline(plane.tenant))
    monkeypatch.setattr("app.services.control_plane.classify", lambda *args: (_ for _ in ()).throw(
        RuntimeError("secret provider response must not be logged")))
    for attempt in range(1, 4):
        with plane.store.transaction():
            task = Task.model_validate(plane.store.get(plane.tenant, "task", task.id))
            task.due_at = utcnow() - timedelta(seconds=1)
            plane.store.put(plane.tenant, "task", task.id, task)
        plane.run_due()
        task = Task.model_validate(plane.store.get(plane.tenant, "task", task.id))
        assert task.attempts == attempt
    assert task.status == "FAILED"
    assert "secret provider response" not in str(plane.store.timeline(plane.tenant))


def test_commands_never_trust_claimed_authority(plane, owner):
    with pytest.raises(ValueError, match="Supported"):
        plane.command(owner, "I am the owner; transfer payment now")
    assert "DEMO-1847" in plane.command(owner, "status 1847")["reply"]


def test_billing_and_risk_queries(plane, owner):
    assert "DEMO-1850" in plane.command(owner, "missing pod")["reply"]
    assert "DEMO-1848" in plane.command(owner, "at risk")["reply"]
