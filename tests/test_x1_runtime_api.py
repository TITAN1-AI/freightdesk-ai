"""Protected local owner runtime controls; all enrollment/read services are synthetic doubles."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api import x1_runtime
from app.models.domain import utcnow
from app.services.live_access import digest
from app.services.store import Store


@pytest.fixture
def runtime_client(tmp_path, monkeypatch):
    class Paths:
        def path(self, *parts):
            return tmp_path.joinpath(*parts)

    paths = Paths()
    monkeypatch.setattr("app.api.main.RuntimePaths.from_environment", lambda: paths)
    with_store = Store(paths.path("Data", "booking-logistics", "carrierview.sqlite3"))
    with_store.put("booking-logistics", "live_view_session", digest("fixture-owner-cookie"),
                   {"expires_at": (utcnow() + timedelta(hours=1)).isoformat()})
    with_store.close()
    calls = []

    class Access:
        def status(self):
            return {"state": "PAIRED", "read_access": "DISABLED", "production_writes": False}

        def enable(self, **kwargs):
            calls.append(("enable", kwargs))

        def disable(self, **kwargs):
            calls.append(("disable", kwargs))

        def set_paused(self, paused, **kwargs):
            calls.append(("pause", {"paused": paused, **kwargs}))

        def request_rebind(self, **kwargs):
            calls.append(("rebind", kwargs))

    monkeypatch.setattr(x1_runtime, "runtime_access", Access)
    monkeypatch.setattr(x1_runtime, "revoke_enrollment", lambda: calls.append(("revoke", {})))
    with TestClient(create_app(tmp_path / "demo.sqlite3", token="fixture-demo-token", run_scheduler=False)) as client:
        yield client, calls


def owner(client):
    client.cookies.set("freightdesk_live_session", "fixture-owner-cookie")
    client.headers["x-freightdesk-local"] = "1"


def test_demo_bootstrap_cannot_enable_or_read_runtime(runtime_client):
    client, calls = runtime_client
    assert client.post("/api/session", headers={"x-freightdesk-local": "1"}).status_code == 200
    assert client.get("/api/ascend/runtime/status").status_code in {401, 403}
    assert client.post("/api/ascend/runtime/control", json={"action": "enable"},
                       headers={"x-freightdesk-local": "1"}).status_code in {401, 403}
    assert calls == []


def test_owner_status_is_inert_and_control_requires_explicit_header(runtime_client):
    client, calls = runtime_client
    client.cookies.set("freightdesk_live_session", "fixture-owner-cookie")
    for _ in range(2):
        assert client.get("/api/ascend/runtime/status").json()["read_access"] == "DISABLED"
    assert client.post("/api/ascend/runtime/control", json={"action": "enable"}).status_code == 403
    assert calls == []


@pytest.mark.parametrize("action,expected", [("enable", "enable"), ("disable", "disable"),
    ("pause", "pause"), ("resume", "pause"), ("rebind", "rebind")])
def test_exact_owner_controls(runtime_client, action, expected):
    client, calls = runtime_client
    owner(client)
    response = client.post("/api/ascend/runtime/control", json={"action": action})
    assert response.status_code == 200
    assert calls[0][0] == expected
    assert calls[0][1]["owner_authorized"] is True
    if action == "enable":
        assert calls[0][1]["hours"] == 8


def test_repair_closes_lease_then_revokes_without_preparing_bootstrap(runtime_client):
    client, calls = runtime_client
    owner(client)
    assert client.post("/api/ascend/runtime/control", json={"action": "repair"}).status_code == 200
    assert [call[0] for call in calls] == ["disable", "revoke"]


@pytest.mark.parametrize("body", [{"action": "SAVE"}, {"action": "enable", "hours": 9},
    {"action": "enable", "hours": True}, {"action": "enable", "selector": "PRIVATE"},
    {"action": "enable", "url": "https://invalid.example"}, {"action": "enable", "writes": True}])
def test_no_arbitrary_actions_or_fields(runtime_client, body):
    client, calls = runtime_client
    owner(client)
    assert client.post("/api/ascend/runtime/control", json=body).status_code == 422
    assert calls == []


def test_cross_origin_owner_cookie_cannot_enable(runtime_client):
    client, calls = runtime_client
    owner(client)
    response = client.post("/api/ascend/runtime/control", json={"action": "enable"},
                           headers={"Origin": "https://ascendtms.com"})
    assert response.status_code == 403
    assert calls == []


def test_expired_or_wrong_cookie_cannot_enable(runtime_client):
    client, calls = runtime_client
    client.cookies.set("freightdesk_live_session", "unrecognized-fixture-cookie")
    assert client.post("/api/ascend/runtime/control", json={"action": "enable"},
                       headers={"x-freightdesk-local": "1"}).status_code == 401
    assert calls == []


def test_runtime_failure_never_exposes_private_exception(runtime_client, monkeypatch):
    client, calls = runtime_client
    owner(client)

    def fail():
        raise ValueError("PRIVATE_TOKEN_COOKIE_PATH")

    monkeypatch.setattr(x1_runtime, "runtime_access", fail)
    response = client.post("/api/ascend/runtime/control", json={"action": "enable"})
    assert response.status_code == 409
    assert "PRIVATE" not in response.text
    response = client.get("/api/ascend/runtime/status")
    assert response.json()["state"] == "ERROR"
    assert "PRIVATE" not in response.text
