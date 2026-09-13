import asyncio

import httpx
import pytest

from app.services.carrierview_historical import collect_historical
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.errors import ContractMismatch
from tests.carrierview_fixtures import config, contract


@pytest.mark.parametrize("wrong_identity", [False, True])
def test_exact_historical_sequence_and_identity_stop(wrong_identity):
    calls = []
    candidate = {"id": "fixture-42", "load_id": "TEST-42", "driver_phone": "SYNTHETIC",
                 "integration_type": "carrier_view",
                 "locations": {kind: {"address": "Fixture", "date_to": "2026-09-04T16:00:00Z",
                                      "timezone_name": "America/Chicago"}
                               for kind in ("pickup", "destination")}}
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"success": True, "data":
            {**candidate, "load_id": "WRONG" if wrong_identity else "TEST-42"}})
    async def run():
        async with CarrierViewAdapter(config(discovery_provider_id="fixture-42"), contract(), lambda _: None,
                                      httpx.MockTransport(respond)) as adapter:
            if wrong_identity:
                with pytest.raises(ContractMismatch):
                    await collect_historical(adapter, candidate, "TEST-42", lambda *_: None)
            else:
                result = await collect_historical(adapter, candidate, "TEST-42", lambda *_: None)
                assert not result["imported"] and not result["ui_reconciled"]
            with pytest.raises(PermissionError):
                await adapter._request("GET", "/api/loads/other", "exact_load_discovery", discovery=True)
    asyncio.run(run())
    assert len(calls) == (1 if wrong_identity else 3)
    assert all(call.method == "GET" and call.url.path.startswith("/api/loads/fixture-42") for call in calls)
