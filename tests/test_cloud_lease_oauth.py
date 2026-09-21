"""Cloud lease OAuth device-code rehearsal. Does not mint demo sessions."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.cloud_lease_oauth import CloudLeaseOAuthService, DEVICE_GRANT
from app.services.store import Store
from tests.test_portable_leases import EXT_ORIGIN, portable_headers, sign_in, snapshot

OAUTH = "/v1/portable/oauth"


def test_oauth_catalog_keeps_placeholder_as_the_only_demo_mint(client):
    client.headers.pop("Authorization", None)
    response = client.get(OAUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["cloud_idp"] == "NOT_CONFIGURED"
    assert body["mints_session_from_oauth"] is False
    assert body["replaces_placeholder"] is False
    assert body["demo_sign_in_unchanged"] is True
    assert body["live_validated"] is False
    assert body["production_writes"] is False
    assert body["placeholder_session"]["implemented"] is True
    assert body["placeholder_session"]["route"] == "POST /v1/portable/session"
    assert body["agent_bearer"]["not_oauth"] is True
    assert body["device_code"]["mints_session"] is False
    assert body["authorization_code_pkce"]["implemented"] is False
    cors = client.get(OAUTH, headers={"Origin": EXT_ORIGIN})
    assert cors.status_code == 200
    assert cors.headers["access-control-allow-origin"] == EXT_ORIGIN
    denied = client.get(OAUTH, headers={"Origin": "https://ascendtms.com"})
    assert denied.status_code == 403


def test_device_code_rehearsal_never_mints_and_does_not_break_demo_sign_in(client):
    client.headers.pop("Authorization", None)
    assert client.post(OAUTH + "/device/start").status_code == 403
    started = client.post(OAUTH + "/device/start", headers=portable_headers())
    assert started.status_code == 200
    payload = started.json()
    assert payload["mints_session"] is False
    assert payload["cloud_idp"] == "NOT_CONFIGURED"
    assert payload["auth_kind"] == "DEVICE_CODE"
    assert "device_token" not in payload
    assert "lease_token" not in payload
    assert "agent_token" not in payload
    assert payload["grant_type"] == DEVICE_GRANT
    assert "-" in payload["user_code"]

    pending = client.post(OAUTH + "/device/poll", json={"device_code": payload["device_code"]},
                          headers=portable_headers())
    assert pending.status_code == 409
    assert pending.json()["detail"] == "authorization_pending"

    aliased = client.post(OAUTH + "/token", json={
        "grant_type": DEVICE_GRANT,
        "device_code": payload["device_code"],
    }, headers=portable_headers())
    assert aliased.status_code == 409
    assert aliased.json()["detail"] == "authorization_pending"

    token = sign_in(client)
    created = client.post("/v1/portable/leases", json={
        "origin": "https://ascendtms.com",
        "scope": "VISIBLE_BOARD_ONLY",
        "ttl_seconds": 900,
    }, headers=portable_headers(token=token))
    assert created.status_code == 200
    lease = created.json()
    accepted = client.post("/v1/portable/harvest", json=snapshot(lease["id"]),
                           headers=portable_headers(token=lease["lease_token"]))
    assert accepted.status_code == 200
    status = client.get("/v1/portable/status", headers=portable_headers(token=token)).json()
    assert status["auth_kind"] == "PLACEHOLDER"
    assert status["signed_in"] is True


def test_authorize_and_cloud_revoke_are_not_configured(client):
    client.headers.pop("Authorization", None)
    authorize = client.post(OAUTH + "/authorize", json={
        "response_type": "code",
        "code_challenge": "a" * 43,
        "code_challenge_method": "S256",
        "redirect_uri": "https://cloud.freightdesk.example/callback",
    }, headers=portable_headers())
    assert authorize.status_code == 409
    assert authorize.json()["detail"] == "cloud_idp_not_configured"
    code_grant = client.post(OAUTH + "/token", json={
        "grant_type": "authorization_code",
        "code": "not-a-real-code",
    }, headers=portable_headers())
    assert code_grant.status_code == 409
    assert code_grant.json()["detail"] == "cloud_idp_not_configured"
    refresh = client.post(OAUTH + "/token", json={"grant_type": "refresh_token"},
                          headers=portable_headers())
    assert refresh.status_code == 409
    assert refresh.json()["detail"] == "cloud_idp_not_configured"
    unknown = client.post(OAUTH + "/token", json={"grant_type": "password"},
                          headers=portable_headers())
    assert unknown.status_code == 409
    assert unknown.json()["detail"] == "unsupported_grant_type"
    revoke = client.post(OAUTH + "/revoke", headers=portable_headers())
    assert revoke.status_code == 409
    assert revoke.json()["detail"] == "cloud_idp_not_configured"
    verify = client.get(OAUTH + "/device/verify")
    assert verify.status_code == 200
    assert verify.json()["placeholder_session_required"] is True
    assert verify.json()["mints_session"] is False


def test_unknown_and_expired_device_codes_fail_closed(tmp_path, monkeypatch):
    now = datetime(2026, 9, 21, tzinfo=timezone.utc)
    monkeypatch.setattr("app.services.cloud_lease_oauth.utcnow", lambda: now)
    store = Store(tmp_path / "oauth.sqlite3")
    service = CloudLeaseOAuthService(store, "booking-logistics")
    started = service.start_device_authorization()
    with pytest.raises(ValueError, match="invalid_grant"):
        service.poll_device("not-a-issued-device-code-value")
    monkeypatch.setattr("app.services.cloud_lease_oauth.utcnow",
                        lambda: now + timedelta(minutes=16))
    with pytest.raises(ValueError, match="expired_token"):
        service.poll_device(started["device_code"], DEVICE_GRANT)
    catalog = service.catalog()
    assert catalog["mints_session_from_oauth"] is False
    store.close()
