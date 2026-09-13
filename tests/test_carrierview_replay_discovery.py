import asyncio

import httpx
import pytest

from app.services.carrierview_replay_discovery import SERVICE_REASON, company_matches, discover_past
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.config import CredentialClass
from tests.carrierview_fixtures import config, contract


@pytest.mark.parametrize("company,expected_calls", [("Booking Logistics LLC", 2), ("Other LLC", 1), (None, 1)])
def test_company_gate_and_past_filter(company, expected_calls):
    requests, audits = [], []
    def respond(request):
        requests.append(request)
        if request.url.path == "/api/profile":
            return httpx.Response(200, json={"success": True, "data": {"company": {"name": company}}})
        assert request.method == "GET" and request.url.query == b"filter=past"
        return httpx.Response(200, json={"success": True, "loads": [{"id": 123, "load_id": "TEST-42"}]})
    async def run():
        async with CarrierViewAdapter(config(credential_class=CredentialClass.TENANT,
                elevation_reason=SERVICE_REASON), contract(), audits.append, httpx.MockTransport(respond)) as adapter:
            return await discover_past(adapter, lambda *_: None)
    result = asyncio.run(run())
    assert len(requests) == expected_calls
    assert not result["imported"]
    assert all(entry["credential_class"] == "tenant" for entry in audits)


def test_conflicting_company_identity_rejected():
    assert not company_matches({"company_name": "Other LLC", "company": {"name": "Booking Logistics LLC"}})


def test_agent_network_disabled_even_when_read_flags_enabled():
    async def run():
        async with CarrierViewAdapter(config(origin_verified=True, network_reads_authorized=True,
                discovery_reads_authorized=True), contract(), lambda _: None) as adapter:
            with pytest.raises(PermissionError, match="Agent credential"):
                await adapter._request("GET", "/api/profile", "profile_discovery", discovery=True)
    asyncio.run(run())
