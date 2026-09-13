from copy import deepcopy
from datetime import datetime

import pytest

from app.models.domain import utcnow
from app.services.carrierview_poc import candidate_hash, live_projection
from app.services.historical_import import PROVEN, build_historical, import_historical
from app.services.live_access import issue_grant, redeem_grant, session_valid
from tests.test_historical_report import example


def evidence():
    candidate, detail = example()
    candidate.update(id="fixture", load_id="TEST-42")
    detail.update(delivery_arrived=True, delivery_departed=True, client_url="https://example.invalid/private")
    bundle = {"fixture": False, "candidate": candidate, "detail": {"success": True, "data": detail},
              "position": {"success": True, "data": {"position": {"created_at_utc": 123}}},
              "history": {"success": True, "data": {"positions": [], "pagination": {"total": 0}}},
              "observed_at": utcnow().isoformat()}
    confirmation = {"approved": True, "booking_reference": "TEST-42", "provider_id": "fixture",
        "reviewed_by": "test-owner", "reviewed_at": utcnow().isoformat(),
        "stops": {kind: {"appointment_start": "2026-09-04T06:00-05:00",
                        "appointment_end": "2026-09-04T11:00-05:00",
                        "arrived_at": "2026-09-04T07:00-05:00", "departed_at": "2026-09-04T08:00-05:00"}
                  for kind in ("pickup", "destination")}}
    confirmation["evidence_hash"] = candidate_hash(bundle)
    return bundle, confirmation


def test_historical_import_is_scoped_idempotent_and_preserves_unknowns(plane):
    bundle, confirmation = evidence()
    before = len(plane.store.all(plane.tenant, "task"))
    assert import_historical(plane.store, bundle, confirmation)["status"] == "IMPORTED"
    assert import_historical(plane.store, bundle, confirmation)["status"] == "ALREADY_IMPORTED"
    assert len(plane.store.all(plane.tenant, "task")) == before
    value = plane.store.get(plane.tenant, "shipment", "live-poc-001")
    assert value["customer"] is None and value["driver"] is None
    assert value["status"] == "DELIVERED" and value["paused"] and value["human_takeover"]
    assert value["tracking"]["accepted"] is None and value["documents"] == []
    view = live_projection(plane.store, plane.tenant)
    assert view["shipment"]["historical"] and view["capability_matrix"] == PROVEN
    assert not view["capability_matrix"]["POD"] and not view["capability_matrix"]["Real-time monitoring"]
    assert "private" not in str(view) and "FIXTURE" not in str(view)
    assert len([e for e in plane.store.timeline(plane.tenant) if e["event"] == "HISTORICAL_POC_IMPORTED"]) == 1


@pytest.mark.parametrize("change", ["fixture", "hash", "approval", "identity", "ui_time"])
def test_historical_import_rejects_unverified_or_changed_evidence(change):
    bundle, confirmation = evidence()
    if change == "fixture":
        bundle["fixture"] = True
        confirmation["evidence_hash"] = candidate_hash(bundle)
    elif change == "hash":
        bundle["detail"]["data"]["driver_phone"] = "CHANGED"
    elif change == "approval":
        confirmation["approved"] = False
    elif change == "identity":
        confirmation["booking_reference"] = "OTHER"
    else:
        confirmation["stops"]["pickup"]["arrived_at"] = "2026-09-04T08:00-05:00"
    with pytest.raises(PermissionError):
        build_historical(bundle, confirmation)


def test_historical_approval_is_not_subject_to_realtime_snapshot_expiry():
    bundle, confirmation = evidence()
    bundle["observed_at"] = datetime.fromisoformat("2026-09-01T00:00:00+00:00").isoformat()
    confirmation["evidence_hash"] = candidate_hash(bundle)
    assert build_historical(bundle, confirmation).workflow == "historical_production_replay"


def test_one_use_live_grant_cannot_be_replayed_or_used_as_session(plane):
    bundle, confirmation = evidence()
    import_historical(plane.store, bundle, confirmation)
    grant = issue_grant(plane.store, plane.tenant)
    assert not session_valid(plane.store, plane.tenant, grant)
    session = redeem_grant(plane.store, plane.tenant, grant)
    assert session_valid(plane.store, plane.tenant, session)
    assert not session_valid(plane.store, "other-tenant", session)
    with pytest.raises(PermissionError):
        redeem_grant(plane.store, plane.tenant, grant)
    changed = deepcopy(bundle)
    changed["observed_at"] = utcnow().isoformat()
    confirmation["evidence_hash"] = candidate_hash(changed)
    with pytest.raises(PermissionError):
        import_historical(plane.store, changed, confirmation)


def test_http_live_session_requires_private_grant_not_demo_cookie(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.main import create_app
    from app.core.runtime import RuntimePaths
    from app.services.store import Store
    class TestPaths:
        def path(self, *parts):
            return tmp_path / "live.sqlite3"
    monkeypatch.setattr(RuntimePaths, "from_environment", lambda: TestPaths())
    store = Store(tmp_path / "live.sqlite3")
    bundle, confirmation = evidence()
    import_historical(store, bundle, confirmation)
    grant = issue_grant(store, "booking-logistics")
    store.close()
    with TestClient(create_app(tmp_path / "demo.sqlite3", token="test-token", run_scheduler=False)) as client:
        client.post("/api/session", headers={"X-FreightDesk-Local": "1"})
        assert client.get("/api/carrierview/poc").status_code == 403
        response = client.post("/api/carrierview/live-session", json={"grant": grant})
        assert response.status_code == 200
        assert "HttpOnly" in response.headers["set-cookie"] and "SameSite=strict" in response.headers["set-cookie"]
        result = client.get("/api/carrierview/poc")
        assert result.status_code == 200 and result.json()["shipment"]["historical"]
        assert client.post("/api/carrierview/live-session", json={"grant": grant}).status_code == 401
