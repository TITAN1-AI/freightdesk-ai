import asyncio
import json

import httpx
import pytest

from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.config import CarrierViewConfig, CredentialClass
from integrations.carrierview.errors import CarrierViewError, ContractMismatch, ScopeElevationRequired
from integrations.carrierview.schemas import DriverTextMessage, CreateTrackingLoad
from tests.carrierview_fixtures import PROVIDER_ID, config, contract, provider_load


def test_all_documented_reads_use_expected_paths_and_bearer():
    requests, audits = [], []
    load = provider_load()
    def handler(request):
        requests.append(request)
        assert request.headers["authorization"] == "Bearer SYNTHETIC-AGENT-TOKEN"
        assert request.headers["content-type"] == "application/json"
        data = {"id": "fixture-user", "company_id": "fixture-company"}
        if request.url.path.endswith("integration-types"):
            data = ["carrier_view"]
        elif request.url.path.endswith("positions-history"):
            data = [load["last_position"]] * 5
        elif request.url.path.endswith("last-position"):
            data = None
        elif request.url.path == "/api/loads":
            assert str(request.url.query) == "b'filter=active'"
            data = [load]
        elif request.url.path.endswith(PROVIDER_ID):
            data = load
        return httpx.Response(200, json={"success": True, "data": data})
    async def run():
        async with CarrierViewAdapter(config(), contract(), audits.append, httpx.MockTransport(handler)) as client:
            assert (await client.get_profile()).data.id == "fixture-user"
            await client.get_integration_types()
            assert (await client.search_loads()).data[0].id == PROVIDER_ID
            assert (await client.get_load(PROVIDER_ID)).data.load_id == "TEST-1847"
            assert (await client.get_last_position(PROVIDER_ID)).data is None
            assert len((await client.get_positions_history(PROVIDER_ID, 2)).data) == 2
    asyncio.run(run())
    assert len(requests) == 6
    assert all(r.method == "GET" for r in requests)
    assert "SYNTHETIC-AGENT-TOKEN" not in json.dumps(audits)
    assert all(a["credential_class"] == "agent" for a in audits)


@pytest.mark.parametrize("code", ["user_not_found", "company_not_found", "company_disabled", "load_not_found",
    "permission_denied", "required_fields_errors", "creation_error", "driver_opted_out",
    "sms_provider_failed", "internal_error"])
def test_http_200_failure_is_never_success_or_automatically_retried(code):
    calls, audits = [], []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"success": False, "error_code": code,
                                        "errors": {"message": "SENSITIVE-INPUT-DO-NOT-LOG"}})
    async def run():
        async with CarrierViewAdapter(config(), contract(), audits.append, httpx.MockTransport(handler)) as client:
            with pytest.raises(CarrierViewError) as caught:
                await client.get_profile()
            assert caught.value.code == code
            assert caught.value.errors["message"] == "SENSITIVE-INPUT-DO-NOT-LOG"
            assert "SENSITIVE-INPUT" not in str(caught.value)
            if code == "permission_denied":
                assert isinstance(caught.value, ScopeElevationRequired)
    asyncio.run(run())
    assert len(calls) == 1
    assert "SENSITIVE-INPUT" not in json.dumps(audits)


@pytest.mark.parametrize("envelope", [{}, {"success": 1}, {"success": "true"}, {"success": None}])
def test_invalid_success_envelope_fails_closed(envelope):
    async def run():
        async with CarrierViewAdapter(config(), contract(), lambda _: None,
                httpx.MockTransport(lambda _: httpx.Response(200, json=envelope))) as client:
            with pytest.raises(ContractMismatch):
                await client.get_profile()
    asyncio.run(run())


def test_redirects_never_forward_credentials():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://unapproved.example.invalid"})
    async def run():
        async with CarrierViewAdapter(config(), contract(), lambda _: None, httpx.MockTransport(handler)) as client:
            with pytest.raises(CarrierViewError, match="redirect_rejected"):
                await client.get_profile()
    asyncio.run(run())
    assert len(calls) == 1


def test_rate_limit_is_explicit_and_not_retried():
    async def run():
        async with CarrierViewAdapter(config(), contract(), lambda _: None,
                httpx.MockTransport(lambda _: httpx.Response(429, headers={"Retry-After": "45"}))) as client:
            with pytest.raises(CarrierViewError) as caught:
                await client.get_profile()
            assert caught.value.retry_after_seconds == 45
            assert caught.value.code == "rate_limited"
    asyncio.run(run())


def test_no_network_without_explicit_authorization_and_contract():
    async def run():
        async with CarrierViewAdapter(config(credential_class=CredentialClass.TENANT,
                elevation_reason="Synthetic explicit tenant selection"), contract(), lambda _: None) as client:
            with pytest.raises(PermissionError, match="Owner read authorization"):
                await client.get_profile()
            with pytest.raises(PermissionError, match="Production CarrierView writes"):
                client.authorize_transport("POST")
    asyncio.run(run())


def test_agent_credentials_never_fall_back(monkeypatch):
    monkeypatch.setenv("CARRIERVIEW_TENANT_API_TOKEN", "TENANT-SYNTHETIC")
    monkeypatch.setenv("CARRIERVIEW_API_TOKEN", "LEGACY-SYNTHETIC")
    with pytest.raises(ValueError, match="CARRIERVIEW_AGENT_API_TOKEN"):
        CarrierViewConfig.from_environment()
    monkeypatch.setenv("CARRIERVIEW_AGENT_API_TOKEN", "AGENT-SYNTHETIC")
    monkeypatch.setenv("CARRIERVIEW_BASE_URL", "https://example.invalid")
    assert CarrierViewConfig.from_environment().api_token.get_secret_value() == "AGENT-SYNTHETIC"
    with pytest.raises(ValueError, match="elevation reason"):
        CarrierViewConfig.from_environment(CredentialClass.TENANT)


def test_tenant_selection_distinct_in_audit():
    audits = []
    async def run():
        selected = config(credential_class="tenant", elevation_reason="fixture approved scope test")
        async with CarrierViewAdapter(selected, contract(), audits.append,
                httpx.MockTransport(lambda _: httpx.Response(200, json={"success": True, "data": {"id": "fixture"}}))) as client:
            await client.get_profile()
    asyncio.run(run())
    assert all(a["credential_class"] == "tenant" and a["elevated"] for a in audits)


@pytest.mark.parametrize("provider_id", ["../profile", "abc?token=x", "abc/def", ""])
def test_provider_id_cannot_escape_documented_route(provider_id):
    with pytest.raises(ValueError):
        CarrierViewAdapter.provider_id(provider_id)


@pytest.mark.parametrize("body", [{"message_type": "custom"}, {"message_type": "custom", "message": " "},
    {"message_type": "custom", "message": "x" * 481}, {"message_type": "undocumented"}])
def test_sms_validation(body):
    with pytest.raises(ValueError):
        DriverTextMessage.model_validate(body)


def test_creation_requires_both_stops_and_native_tracking():
    with pytest.raises(ValueError):
        CreateTrackingLoad(driver_phone="+15550100000", load_id="TEST",
            locations=[{"type": "pickup", "address": "A"}, {"type": "pickup", "address": "B"}])
    payload = CreateTrackingLoad(driver_phone="+15550100000", load_id="TEST",
        locations=[{"type": "pickup", "address": "A"}, {"type": "destination", "address": "B"}])
    assert payload.model_dump(exclude_none=True)["integration_type"] == "carrier_view"
