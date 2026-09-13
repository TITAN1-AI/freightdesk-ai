import asyncio

import httpx
import pytest

from app.models.domain import utcnow
from app.services.carrierview_poc import ReadPlan, UiReconciliation, import_reconciled_poc, stage_readonly_poc
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.errors import ContractMismatch
from tests.carrierview_fixtures import PROVIDER_ID, config, contract, plan_parts


def staged_probe(plane, *, mismatch=False, history=False):
    load, canonical, expected = plan_parts()
    raw_load = load.model_dump(exclude_unset=True)
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path == "/api/profile":
            data = {"id": "different-user" if mismatch else "fixture-user", "company_id": "fixture-company"}
        elif request.url.path == "/api/loads":
            data = [raw_load]
        elif request.url.path.endswith("positions-history"):
            data = [raw_load["last_position"]]
        elif request.url.path.endswith("last-position"):
            data = raw_load["last_position"]
        else:
            data = raw_load
        return httpx.Response(200, json={"success": True, "data": data})
    plan = ReadPlan(expected_user_id="fixture-user", expected_company_id="fixture-company",
                    identity=expected, canonical=canonical, include_history=history)
    async def run():
        async with CarrierViewAdapter(config(), contract(), lambda _: None, httpx.MockTransport(handler)) as adapter:
            return await stage_readonly_poc(adapter, plan, plane.store)
    return run, requests


def test_bounded_poc_sequence_stages_without_import_or_live_claim(plane):
    run, requests = staged_probe(plane, history=True)
    result = asyncio.run(run())
    assert result["status"] == "AWAITING_UI_RECONCILIATION" and not result["live_validated"]
    assert [r.url.path for r in requests] == [
        "/api/profile", "/api/loads", f"/api/loads/{PROVIDER_ID}",
        f"/api/loads/{PROVIDER_ID}/last-position", f"/api/loads/{PROVIDER_ID}/positions-history"]
    assert all(r.method == "GET" for r in requests)
    assert plane.store.all(plane.tenant, "live_poc") == []


def test_wrong_profile_stops_before_reading_loads(plane):
    run, requests = staged_probe(plane, mismatch=True)
    with pytest.raises(ContractMismatch, match="account_identity_mismatch"):
        asyncio.run(run())
    assert len(requests) == 1


def test_synthetic_evidence_never_becomes_live_validated(plane):
    run, _ = staged_probe(plane)
    staged = asyncio.run(run())
    with pytest.raises(PermissionError, match="Synthetic fixture"):
        import_reconciled_poc(plane.store, plane.tenant, UiReconciliation(
            candidate_hash=staged["candidate_hash"], reviewed_by="fixture-owner", reviewed_at=utcnow(),
            identity_matches=True, tracking_values_match=True))


def test_demo_cookie_cannot_unlock_live_view(client):
    client.headers.pop("Authorization")
    assert client.post("/api/session", headers={"X-FreightDesk-Local": "1"}).status_code == 200
    assert client.get("/api/carrierview/poc").status_code == 403
