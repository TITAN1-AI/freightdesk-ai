"""Demo agent Bearer sessions for the Ascend facade. Not LIVE_VALIDATED."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.services.agent_sessions import AgentSessionService
from app.services.store import Store
from tests.test_portable_leases import portable_headers, sign_in, snapshot


def mint_agent(client):
    client.headers.pop("Authorization", None)
    response = client.post("/v1/agent/session")
    assert response.status_code == 200
    body = response.json()
    assert body["auth_kind"] == "DEMO_AGENT"
    assert body["mode"] == "demo"
    assert body["live_validated"] is False
    assert body["production_writes"] is False
    assert body["not_oauth"] is True
    assert body["bootstrap_path"] == "Tokens/demo-agent-token.txt"
    assert len(body["agent_token"]) >= 32
    return body["agent_token"]


def test_agent_status_unsigned_does_not_leak_token(client):
    client.headers.pop("Authorization", None)
    response = client.get("/v1/agent/status")
    assert response.status_code == 200
    body = response.json()
    assert body["signed_in"] is False
    assert body["auth_kind"] == "DEMO_AGENT"
    assert body["bootstrap_path"] == "Tokens/demo-agent-token.txt"
    assert "agent_token" not in body
    assert body["live_validated"] is False
    assert body["production_writes"] is False


def test_agent_bearer_reads_empty_facade(client):
    token = mint_agent(client)
    headers = {"Authorization": f"Bearer {token}"}
    status = client.get("/v1/ascend/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["harvest_available"] is False
    loads = client.get("/v1/ascend/loads", headers=headers)
    assert loads.status_code == 200
    assert loads.json()["loads"] == []
    assert loads.json()["live_validated"] is False
    session = client.get("/v1/agent/session", headers=headers)
    assert session.status_code == 200
    assert session.json()["signed_in"] is True
    assert "agent_token" not in session.json()


def test_agent_bearer_rejected_when_missing_or_invalid(client):
    client.headers.pop("Authorization", None)
    assert client.get("/v1/ascend/status").status_code == 401
    assert client.get("/v1/ascend/loads").status_code == 401
    assert client.get("/v1/agent/session").status_code == 401
    bad = {"Authorization": "Bearer not-an-agent-token"}
    assert client.get("/v1/ascend/loads", headers=bad).status_code == 401
    assert client.get("/v1/agent/session", headers=bad).status_code == 401
    denied = client.post("/v1/portable/leases", json={"origin": "https://ascendtms.com"},
                         headers=bad)
    assert denied.status_code == 401


def test_agent_bearer_reads_facade_after_extension_harvest(client):
    device = sign_in(client)
    lease = client.post("/v1/portable/leases", json={"origin": "https://ascendtms.com"},
                        headers=portable_headers(token=device)).json()
    accepted = client.post("/v1/portable/harvest", json=snapshot(lease["id"]),
                           headers=portable_headers(token=lease["lease_token"]))
    assert accepted.status_code == 200
    token = mint_agent(client)
    board = client.get("/v1/ascend/loads", headers={"Authorization": f"Bearer {token}"})
    assert board.status_code == 200
    assert board.json()["loads"][0]["load_id"] == "1763"
    assert board.json()["live_validated"] is False
    assert board.json()["production_writes"] is False


def test_agent_can_create_lease_then_read_harvested_facade(client):
    token = mint_agent(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post("/v1/portable/leases", json={
        "origin": "https://ascendtms.com",
        "scope": "VISIBLE_BOARD_ONLY",
        "ttl_seconds": 900,
    }, headers=headers)
    assert created.status_code == 200
    lease = created.json()
    accepted = client.post("/v1/portable/harvest", json=snapshot(lease["id"]),
                           headers={"Authorization": f"Bearer {lease['lease_token']}"})
    assert accepted.status_code == 200
    board = client.get("/v1/ascend/loads", headers=headers)
    assert board.json()["load_count"] == 1
    status = client.get("/v1/portable/status", headers=headers).json()
    assert status["signed_in"] is True
    assert status["auth_kind"] == "DEMO_AGENT"
    assert status["lease"]["id"] == lease["id"]
    revoked = client.post(f"/v1/portable/leases/{lease['id']}/revoke", headers=headers)
    assert revoked.status_code == 200
    assert client.get("/v1/ascend/loads", headers=headers).json()["loads"][0]["load_id"] == "1763"


def test_agent_token_is_not_a_harvest_lease_token(client):
    token = mint_agent(client)
    denied = client.post("/v1/portable/harvest", json=snapshot("lease-id-value"),
                         headers={"Authorization": f"Bearer {token}"})
    assert denied.status_code == 401
    assert denied.json()["detail"] == "lease_required"


def test_extension_device_session_still_creates_leases(client):
    device = sign_in(client)
    created = client.post("/v1/portable/leases", json={"origin": "https://ascendtms.com"},
                          headers=portable_headers(token=device))
    assert created.status_code == 200
    assert created.json()["status"] == "ACTIVE"


def test_bootstrap_file_reuses_the_same_agent_token(tmp_path):
    bootstrap = tmp_path / "demo-agent-token.txt"
    with TestClient(create_app(tmp_path / "agent.sqlite3", token="test-only-token",
                               run_scheduler=False, agent_bootstrap_path=bootstrap)) as client:
        first = client.post("/v1/agent/session").json()["agent_token"]
        second = client.post("/v1/agent/session").json()["agent_token"]
        assert first == second
        assert bootstrap.read_text(encoding="utf-8").strip() == first
        assert second not in client.get("/v1/agent/status").json().values()


def test_env_agent_token_is_registered(tmp_path, monkeypatch):
    monkeypatch.setenv("FREIGHTDESK_AGENT_TOKEN", "a" * 40)
    store = Store(tmp_path / "agent-env.sqlite3")
    service = AgentSessionService(store, "booking-logistics")
    issued = service.create_or_get()
    assert issued["agent_token"] == "a" * 40
    assert issued["source"] == "environment"
    assert service.has_session("a" * 40)
    store.close()


def test_short_env_agent_token_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("FREIGHTDESK_AGENT_TOKEN", "too-short")
    store = Store(tmp_path / "agent-short.sqlite3")
    service = AgentSessionService(store, "booking-logistics")
    with pytest.raises(ValueError, match="agent_token_too_short"):
        service.create_or_get()
    store.close()


def test_expired_agent_token_is_rejected(tmp_path, monkeypatch):
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)
    monkeypatch.setattr("app.services.agent_sessions.utcnow", lambda: now)
    store = Store(tmp_path / "agent-exp.sqlite3")
    service = AgentSessionService(store, "booking-logistics")
    issued = service.create_or_get()
    monkeypatch.setattr("app.services.agent_sessions.utcnow",
                        lambda: now + timedelta(days=31))
    with pytest.raises(PermissionError, match="agent_session_required"):
        service.require(issued["agent_token"])
    store.close()
