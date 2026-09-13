from datetime import timedelta

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.events.carrierview_webhooks import create_webhook_app
from app.models.domain import utcnow
from app.services.demo import demo_shipments
from tests.carrierview_fixtures import PROVIDER_ID

KEY = "synthetic-local-ingress-key-for-tests-only"


def event(kind="new-position-sent", event_id="fixture-event-1"):
    payload = {"kind": kind, "position": {"timestamp": utcnow().isoformat(), "city": "Fixture City"}}
    if kind == "load-status-changed":
        payload = {"kind": kind, "statuses": {"opaque_status": None}}
    if kind == "chat-message-created-by-driver":
        payload = {"kind": kind, "message_id": "fixture-message", "message": "Fixture driver text"}
    return {"event_id": event_id, "provider_user_id": "fixture-user", "provider_company_id": "fixture-company",
            "provider_load_id": PROVIDER_ID, "occurred_at": utcnow().isoformat(), "payload": payload}


def client_at(path):
    return TestClient(create_webhook_app(local_test_key=SecretStr(KEY), tenant="booking-logistics",
        provider_user_id="fixture-user", provider_company_id="fixture-company", db_path=path))


def seed(client):
    store = client.app.state.inbox.store
    with store.transaction():
        shipment = demo_shipments("booking-logistics")[0]
        store.put("booking-logistics", "shipment", shipment.id, shipment)
        store.put("booking-logistics", "carrierview_load_binding", PROVIDER_ID, {"shipment_id": shipment.id})


def test_all_three_webhook_types_are_quarantined_without_changing_facts(tmp_path):
    with client_at(tmp_path / "inbox.db") as client:
        seed(client)
        before = client.app.state.inbox.store.get("booking-logistics", "shipment", "DEMO-1847")
        for kind in ["new-position-sent", "load-status-changed", "chat-message-created-by-driver"]:
            response = client.post("/webhooks/carrierview/" + kind, json=event(kind),
                                   headers={"X-FreightDesk-Ingress-Key": KEY})
            assert response.status_code == 200
            assert response.json()["status"] == "PENDING_VERIFICATION"
        assert client.app.state.inbox.store.get("booking-logistics", "shipment", "DEMO-1847") == before
        assert len(client.app.state.inbox.store.all("booking-logistics", "webhook_inbox")) == 3


def test_webhook_deduplication_conflicts_and_timestamp_preservation(tmp_path):
    with client_at(tmp_path / "inbox.db") as client:
        seed(client)
        payload = event()
        payload["occurred_at"] = (utcnow() - timedelta(hours=2)).isoformat()
        headers = {"X-FreightDesk-Ingress-Key": KEY}
        path = "/webhooks/carrierview/new-position-sent"
        assert not client.post(path, json=payload, headers=headers).json()["duplicate"]
        assert client.post(path, json=payload, headers=headers).json()["duplicate"]
        stored = client.app.state.inbox.store.all("booking-logistics", "webhook_inbox")[0]
        assert stored["occurred_at"] == payload["occurred_at"]
        payload["payload"]["position"]["city"] = "Another fixture city"
        assert client.post(path, json=payload, headers=headers).status_code == 409


def test_inbox_rejects_wrong_account_unknown_load_and_unauthorized_requests(tmp_path):
    with client_at(tmp_path / "inbox.db") as client:
        seed(client)
        payload = event()
        path = "/webhooks/carrierview/new-position-sent"
        assert client.post(path, json=payload).status_code == 401
        headers = {"X-FreightDesk-Ingress-Key": KEY}
        payload["provider_user_id"] = "different-user"
        assert client.post(path, json=payload, headers=headers).status_code == 403
        payload["provider_user_id"] = "fixture-user"
        payload["provider_load_id"] = "unknown-load"
        assert client.post(path, json=payload, headers=headers).status_code == 404
        assert client.get("/").status_code == 404
        assert client.get("/api/snapshot").status_code == 404


def test_webhook_error_response_does_not_echo_message(tmp_path):
    with client_at(tmp_path / "inbox.db") as client:
        payload = event("chat-message-created-by-driver")
        payload["occurred_at"] = "invalid"
        payload["payload"]["message"] = "SENSITIVE-EXAMPLE"
        result = client.post("/webhooks/carrierview/chat-message-created-by-driver", json=payload,
                             headers={"X-FreightDesk-Ingress-Key": KEY})
        assert result.status_code == 422 and "SENSITIVE-EXAMPLE" not in result.text


def test_body_bound_and_no_public_ingress(tmp_path):
    with client_at(tmp_path / "inbox.db") as client:
        assert client.post("/webhooks/carrierview/new-position-sent", content=b"x" * 128001).status_code == 413
    app = create_webhook_app(local_test_key=SecretStr(KEY), tenant="booking-logistics",
        provider_user_id="u", provider_company_id="c", db_path=tmp_path / "remote.db")
    with TestClient(app, client=("192.0.2.5", 1234)) as client:
        assert client.get("/").status_code == 403
