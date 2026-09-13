import asyncio
import json

import httpx
import pytest

from app.services.carrierview_discovery import candidate_summary, discover_candidates
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.errors import ScopeElevationRequired
from tests.carrierview_fixtures import config, contract


def test_two_gets_only_and_output_redaction():
    requests, evidence = [], {}
    def respond(request):
        requests.append((request.method, request.url.path, request.url.query))
        return httpx.Response(200, json={"success": True, "data": (
            {"email": "private@example.invalid"} if request.url.path == "/api/profile" else
            [{"id": 123, "load_id": "TEST-42", "driver_phone": "+15550100000",
              "client_url": "https://private.invalid/signed", "customer": "PRIVATE_CUSTOMER"}])})
    async def run():
        async with CarrierViewAdapter(config(), contract(), lambda _: None,
                                      httpx.MockTransport(respond)) as adapter:
            return await discover_candidates(adapter, lambda kind, value: evidence.update({kind: value}))
    result = asyncio.run(run())
    assert requests == [("GET", "/api/profile", b""), ("GET", "/api/loads", b"filter=active")]
    assert result["candidates"][0]["booking_load_reference"] == "TEST-42"
    assert not result["imported"] and not result["live_validated"]
    assert set(evidence) == {"profile", "active-loads"}
    assert all(secret not in json.dumps(result) for secret in
               ["private@example", "15550100000", "private.invalid", "PRIVATE_CUSTOMER"])


def test_permission_denial_stops_after_profile():
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"success": False, "error_code": "permission_denied"})
    async def run():
        async with CarrierViewAdapter(config(), contract(), lambda _: None,
                                      httpx.MockTransport(respond)) as adapter:
            await discover_candidates(adapter, lambda *_: None)
    with pytest.raises(ScopeElevationRequired):
        asyncio.run(run())
    assert len(requests) == 1


def test_discovery_does_not_enable_other_paths_or_network():
    async def run():
        async with CarrierViewAdapter(config(), contract(), lambda _: None) as adapter:
            with pytest.raises(PermissionError):
                await adapter._request("GET", "/api/profile", "profile_discovery", discovery=True)
            for method, path in [("POST", "/api/loads"), ("GET", "/api/loads/123")]:
                with pytest.raises(PermissionError):
                    await adapter._request(method, path, "loads_discovery", discovery=True)
    asyncio.run(run())


def test_reference_sanitizer_limits_phone_like_values_and_arbitrary_text():
    result = candidate_summary({"success": True, "loads": [
        {"id": "https://signed.invalid/secret", "load_id": "15550100000"}]})
    assert result["candidates"][0]["provider_id"] == "[withheld]"
    assert result["candidates"][0]["booking_load_reference"] == "[withheld]"
