import asyncio
import json
from datetime import timedelta

import httpx
import pytest

from app.models.domain import ActionPolicy, utcnow
from app.services.action_ledger import ActionLedger
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.errors import CarrierViewError
from integrations.carrierview.schemas import (
    CreateTrackingLoad, DriverChatMessage, DriverTextMessage, EditLoad, WebhookConfiguration,
)
from tests.carrierview_fixtures import PROVIDER_ID, config, contract

PHONE = "+15550100000"


def queued(plane, owner, *, action_id="fixture-action", action_type="send_driver_text_message",
           body=None, policy=ActionPolicy.ALLOW, method="POST", path=None, provider_id=PROVIDER_ID):
    with plane.store.transaction():
        shipment = plane.shipment("DEMO-1847")
        shipment.carrierview_load_id = provider_id
        plane.save(shipment)
    ledger = ActionLedger(plane.store, plane.tenant)
    action = ledger.enqueue(owner, shipment.id, action_id=action_id, recipient=PHONE,
        action_type=action_type, provider_load_id=provider_id, credential_class="agent",
        method=method, path=path or f"/api/loads/{PROVIDER_ID}/text-message",
        payload=body or {"message_type": "welcome"}, policy=policy)
    return ledger, action


@pytest.mark.parametrize("kind", ["create_tracking_load", "edit_load", "disable_load",
    "send_driver_chat_message", "send_driver_text_message", "configure_webhooks"])
def test_all_documented_write_requests_are_fixture_only_and_ledgered(plane, owner, kind):
    pid = PROVIDER_ID
    if kind == "create_tracking_load":
        model = CreateTrackingLoad(load_id="TEST-1847", driver_phone=PHONE,
            locations=[{"type": "pickup", "address": "Fixture A"}, {"type": "destination", "address": "Fixture B"}],
            starts_active=False, emails=["fixture@example.invalid"], dispatchers=[])
        body, path, method, pid = model.model_dump(exclude_none=True), "/api/loads", "POST", None
    elif kind == "edit_load":
        model = EditLoad(load_id="TEST-1847")
        body, path, method = model.model_dump(exclude_unset=True), f"/api/loads/{pid}", "PATCH"
    elif kind == "disable_load":
        model, body, path, method = None, {}, f"/api/loads/{pid}/disable", "PATCH"
    elif kind == "send_driver_chat_message":
        model = DriverChatMessage(message="Fixture message")
        body, path, method = model.model_dump(), f"/api/loads/{pid}/chat-message", "POST"
    elif kind == "send_driver_text_message":
        model = DriverTextMessage(message_type="custom", message="Fixture SMS")
        body, path, method = model.model_dump(), f"/api/loads/{pid}/text-message", "POST"
    else:
        model = WebhookConfiguration(event="new-position-sent", url="https://ingress.example.invalid/positions")
        body, path, method, pid = {"url": model.url}, "/api/webhook/new-position-sent", "PUT", None
    # Empty disable payload is intentional.
    ledger, action = queued(plane, owner, action_type=kind, body=body if body else {"temporary": True},
                             method=method, path=path, provider_id=pid)
    if kind == "disable_load":
        from app.services.action_ledger import payload_hash
        with plane.store.transaction():
            action.payload, action.payload_hash = {}, payload_hash({})
            ledger.save(action)
    requests = []
    def handler(request):
        requests.append(request)
        assert request.method == method and request.url.path == path
        assert json.loads(request.content) == body
        return httpx.Response(200, json={"success": True, "data": {
            "id": "created-fixture-id", "tracking_number_url": "https://example.invalid/driver",
            "client_url": "https://example.invalid/customer"}})
    async def run():
        async with CarrierViewAdapter(config(), contract(), lambda _: None, httpx.MockTransport(handler)) as client:
            async def sender(claimed):
                fn = getattr(client, kind)
                if kind == "disable_load":
                    return await fn(claimed, pid)
                if kind in {"configure_webhooks", "create_tracking_load"}:
                    return await fn(claimed, model)
                return await fn(claimed, pid, model)
            return await ledger.dispatch(owner, action.id, sender, current_policy=ActionPolicy.ALLOW)
    result = asyncio.run(run())
    assert result.state == "SUCCEEDED" and result.attempts == 1 and len(requests) == 1
    if kind == "create_tracking_load":
        saved = ledger.get(action.id)
        assert saved.provider_result["provider_id"] == "created-fixture-id"
        assert saved.provider_result["client_url"].endswith("/customer")


def test_sms_ambiguous_timeout_never_retries(plane, owner):
    ledger, action = queued(plane, owner)
    requests = []
    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout("SENSITIVE-TRANSPORT-CONTENT")
    async def run():
        async with CarrierViewAdapter(config(), contract(), lambda _: None, httpx.MockTransport(handler)) as client:
            async def sender(claimed):
                return await client.send_driver_text_message(claimed, PROVIDER_ID,
                                                               DriverTextMessage(message_type="welcome"))
            result = await ledger.dispatch(owner, action.id, sender, current_policy=ActionPolicy.ALLOW)
            assert result.state == "UNCERTAIN" and result.reconciliation_required and result.completed_at is None
            with pytest.raises(PermissionError, match="unattempted"):
                await ledger.dispatch(owner, action.id, sender, current_policy=ActionPolicy.ALLOW)
    asyncio.run(run())
    assert len(requests) == 1
    assert "SENSITIVE-TRANSPORT" not in str(plane.store.timeline(plane.tenant))


def test_provider_sms_rate_limit_is_not_resent(plane, owner):
    ledger, action = queued(plane, owner)
    async def run():
        async with CarrierViewAdapter(config(), contract(), lambda _: None,
                httpx.MockTransport(lambda _: httpx.Response(429))) as client:
            return await ledger.dispatch(owner, action.id,
                lambda claimed: client.send_driver_text_message(claimed, PROVIDER_ID,
                    DriverTextMessage(message_type="welcome")), current_policy=ActionPolicy.ALLOW)
    result = asyncio.run(run())
    assert result.state == "FAILED" and result.attempts == 1
    assert result.provider_result["error_code"] == "rate_limited"


def test_same_action_id_has_immutable_binding(plane, owner):
    ledger, first = queued(plane, owner)
    assert queued(plane, owner)[1].id == first.id
    with pytest.raises(ValueError, match="different binding"):
        queued(plane, owner, body={"message_type": "installation_guide"})
    assert ledger.get(first.id).payload == first.payload


def test_approval_and_pause_rechecked_before_dispatch(plane, owner):
    ledger, action = queued(plane, owner, policy=ActionPolicy.APPROVAL_REQUIRED)
    async def sender(_):
        return {"success": True}
    with pytest.raises(PermissionError):
        asyncio.run(ledger.dispatch(owner, action.id, sender, current_policy=ActionPolicy.APPROVAL_REQUIRED))
    ledger.approve(owner, action.id)
    plane.set_pause(owner, True)
    with pytest.raises(PermissionError, match="Pause"):
        asyncio.run(ledger.dispatch(owner, action.id, sender, current_policy=ActionPolicy.APPROVAL_REQUIRED))
    assert ledger.get(action.id).attempts == 0


def test_concurrent_claim_dispatches_once(plane, owner):
    ledger, action = queued(plane, owner)
    calls = []
    async def sender(_):
        calls.append(1)
        await asyncio.sleep(0.01)
        return {"success": True}
    async def run():
        return await asyncio.gather(*[
            ledger.dispatch(owner, action.id, sender, current_policy=ActionPolicy.ALLOW) for _ in range(2)
        ], return_exceptions=True)
    results = asyncio.run(run())
    assert len(calls) == 1
    assert sum(isinstance(r, PermissionError) for r in results) == 1


def test_sms_budget_shared_across_actions(plane, owner):
    calls = []
    async def sender(_):
        calls.append(1)
        return {"success": True}
    for index in range(5):
        ledger, action = queued(plane, owner, action_id=f"fixture-{index}")
        asyncio.run(ledger.dispatch(owner, action.id, sender, current_policy=ActionPolicy.ALLOW))
    ledger, action = queued(plane, owner, action_id="fixture-sixth")
    with pytest.raises(CarrierViewError, match="local_sms_rate_limit"):
        asyncio.run(ledger.dispatch(owner, action.id, sender, current_policy=ActionPolicy.ALLOW))
    assert len(calls) == 5 and ledger.get(action.id).attempts == 0


def test_abandoned_action_requires_reconciliation(plane, owner):
    ledger, action = queued(plane, owner)
    with plane.store.transaction():
        action.state, action.attempts, action.last_attempt_at = "IN_FLIGHT", 1, utcnow() - timedelta(minutes=5)
        ledger.save(action)
    assert ledger.recover_abandoned(owner, utcnow() - timedelta(minutes=1)) == 1
    assert ledger.get(action.id).state == "UNCERTAIN"


def test_binding_tamper_blocks_before_transport(plane, owner):
    ledger, action = queued(plane, owner)
    with plane.store.transaction():
        action.payload["message_type"] = "custom"
        ledger.save(action)
    async def sender(_):
        pytest.fail("Transport must not be called")
    with pytest.raises(PermissionError, match="payload hash"):
        asyncio.run(ledger.dispatch(owner, action.id, sender, current_policy=ActionPolicy.ALLOW))
