"""Portable-bridge demo lease API and harvest contract. Not LIVE_VALIDATED."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.portable_leases import PortableLeaseService, validate_harvest_snapshot
from app.services.store import Store

EXT_ORIGIN = "chrome-extension://" + "a" * 32


def snapshot(lease_id, **overrides):
    payload = {
        "lease_id": lease_id,
        "origin": "https://ascendtms.com",
        "view": "ACTIVE_LOADS",
        "view_confidence": "VERIFIED",
        "coverage": "VISIBLE_BOARD_ONLY",
        "evidence_class": "CANDIDATE",
        "live_validated": False,
        "values_included": False,
        "production_writes": False,
        "revision": "ab" * 32,
        "captured_at": "2026-09-15T00:00:00+00:00",
        "row_count": 1,
        "rows": [{"load_id": "1763", "pick_date": "09/15/2026", "drop_date": "09/16/2026",
                  "load_status": "Dispatched"}],
    }
    payload.update(overrides)
    return payload


def portable_headers(origin=EXT_ORIGIN, token=None):
    headers = {"Origin": origin, "X-FreightDesk-Portable": "1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def sign_in(client):
    response = client.post("/v1/portable/session", json={"placeholder": True},
                           headers=portable_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["auth_kind"] == "PLACEHOLDER"
    assert body["live_validated"] is False
    assert body["production_writes"] is False
    return body["device_token"]


def test_status_unsigned_and_demo_gated(client):
    client.headers.pop("Authorization", None)
    response = client.get("/v1/portable/status")
    assert response.status_code == 200
    body = response.json()
    assert body["signed_in"] is False
    assert body["mode"] == "demo"
    assert body["live_validated"] is False
    assert body["production_writes"] is False
    assert body["allowed_origins"] == ["https://ascendtms.com"]
    assert body["lease"] is None


def test_lease_create_harvest_and_revoke(client):
    token = sign_in(client)
    created = client.post("/v1/portable/leases", json={
        "origin": "https://ascendtms.com",
        "scope": "VISIBLE_BOARD_ONLY",
        "ttl_seconds": 900,
    }, headers=portable_headers(token=token))
    assert created.status_code == 200
    lease = created.json()
    assert lease["status"] == "ACTIVE"
    assert lease["live_validated"] is False
    assert "lease_token" in lease
    accepted = client.post("/v1/portable/harvest", json=snapshot(lease["id"]),
                           headers=portable_headers(token=lease["lease_token"]))
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["accepted"] is True
    assert body["row_count"] == 1
    assert body["evidence_class"] == "CANDIDATE"
    assert body["live_validated"] is False
    status = client.get("/v1/portable/status", headers=portable_headers(token=token)).json()
    assert status["signed_in"] is True
    assert status["lease"]["id"] == lease["id"]
    assert status["harvest"]["row_count"] == 1
    revoked = client.post(f"/v1/portable/leases/{lease['id']}/revoke",
                          headers=portable_headers(token=token))
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "REVOKED"
    denied = client.post("/v1/portable/harvest", json=snapshot(lease["id"]),
                         headers=portable_headers(token=lease["lease_token"]))
    assert denied.status_code == 403
    assert denied.json()["detail"] == "lease_revoked"


def test_harvest_payload_validation_rejects_writes_and_private_fields():
    valid = snapshot("lease-id-value")
    validate_harvest_snapshot(valid)
    billed = snapshot("lease-id-value", rows=[{
        "load_id": "1763", "pick_date": "09/15/2026", "drop_date": "09/16/2026",
        "load_status": "To Be Billed",
    }])
    assert validate_harvest_snapshot(billed).rows[0].load_status == "To Be Billed"
    assigned = snapshot("lease-id-value", rows=[{
        "load_id": "1763", "pick_date": "09/15/2026", "drop_date": "09/16/2026",
        "load_status": "Driver Assigned",
    }])
    assert validate_harvest_snapshot(assigned).rows[0].load_status == "Driver Assigned"
    unknown = snapshot("lease-id-value", rows=[{
        "load_id": "1763", "pick_date": "09/15/2026", "drop_date": "09/16/2026",
        "load_status": "UNKNOWN",
    }])
    assert validate_harvest_snapshot(unknown).rows[0].load_status == "UNKNOWN"
    with pytest.raises(ValueError, match="row_status_invalid"):
        validate_harvest_snapshot(snapshot("lease-id-value", rows=[{
            "load_id": "1763", "pick_date": "09/15/2026", "drop_date": "09/16/2026",
            "load_status": "Yeeted",
        }]))
    with pytest.raises(ValueError, match="production_writes_forbidden"):
        validate_harvest_snapshot({**valid, "production_writes": True})
    with pytest.raises(ValueError, match="live_validated_forbidden"):
        validate_harvest_snapshot({**valid, "live_validated": True})
    with pytest.raises(ValueError, match="origin_not_allowlisted"):
        validate_harvest_snapshot({**valid, "origin": "https://evil.example"})
    with pytest.raises(ValueError, match="harvest_payload_invalid"):
        validate_harvest_snapshot({**valid, "rows": [{**valid["rows"][0], "customer": "PRIVATE"}]})
    with pytest.raises(ValueError, match="duplicate_load_id"):
        validate_harvest_snapshot({**valid, "row_count": 2, "rows": valid["rows"] * 2})
    with pytest.raises(ValueError, match="row_count_bound"):
        rows = [{**valid["rows"][0], "load_id": str(1000 + i)} for i in range(101)]
        validate_harvest_snapshot({**valid, "row_count": 101, "rows": rows})


def test_http_harvest_rejects_write_flag(client):
    token = sign_in(client)
    lease = client.post("/v1/portable/leases", json={"origin": "https://ascendtms.com"},
                        headers=portable_headers(token=token)).json()
    response = client.post("/v1/portable/harvest",
                           json=snapshot(lease["id"], production_writes=True),
                           headers=portable_headers(token=lease["lease_token"]))
    assert response.status_code == 409
    assert response.json()["detail"] == "production_writes_forbidden"


def test_lease_rejects_non_allowlisted_origin(client):
    token = sign_in(client)
    response = client.post("/v1/portable/leases", json={
        "origin": "https://not-ascend.example",
        "scope": "VISIBLE_BOARD_ONLY",
    }, headers=portable_headers(token=token))
    assert response.status_code == 409
    assert response.json()["detail"] == "origin_not_allowlisted"


def test_expired_lease_cannot_harvest(tmp_path, monkeypatch):
    now = datetime(2026, 9, 15, tzinfo=timezone.utc)
    monkeypatch.setattr("app.services.portable_leases.utcnow", lambda: now)
    store = Store(tmp_path / "portable.sqlite3")
    service = PortableLeaseService(store, "booking-logistics")
    device = service.create_device_session()
    lease = service.create_lease(device["device_token"], "https://ascendtms.com",
                                 "VISIBLE_BOARD_ONLY", 60)
    monkeypatch.setattr("app.services.portable_leases.utcnow",
                        lambda: now + timedelta(minutes=2))
    with pytest.raises(PermissionError, match="lease_expired"):
        service.accept_harvest(lease["lease_token"], snapshot(lease["id"]))
    store.close()


def test_extension_origin_cors_is_limited_to_portable_prefix(client):
    client.headers.pop("Authorization", None)
    allowed = client.get("/v1/portable/status", headers={"Origin": EXT_ORIGIN})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == EXT_ORIGIN
    preflight = client.options("/v1/portable/harvest", headers={
        "Origin": EXT_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    assert preflight.status_code == 204
    assert preflight.headers["access-control-allow-origin"] == EXT_ORIGIN
    assert client.get("/v1/portable/status",
                      headers={"Origin": "https://ascendtms.com"}).status_code == 403
    assert client.get("/v1/portable/status",
                      headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/snapshot", headers={"Origin": EXT_ORIGIN}).status_code == 403


def test_session_requires_portable_header(client):
    assert client.post("/v1/portable/session", json={"placeholder": True}).status_code == 403
    assert client.post("/v1/portable/leases", json={"origin": "https://ascendtms.com"}).status_code == 401
