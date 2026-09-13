"""Owner-authorized read-only historical replay evidence for Booking reference 1752 only."""
import asyncio
import json

from app.core.runtime import RuntimePaths
from app.models.domain import utcnow
from app.services.carrierview_audit import CarrierViewAudit
from app.services.carrierview_historical import collect_historical, records
from app.services.carrierview_replay_discovery import SERVICE_REASON, company_matches
from app.services.store import Store
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.config import CarrierViewConfig, CredentialClass
from integrations.carrierview.contract import ResponseContract
from integrations.carrierview.errors import CarrierViewError


async def main():
    paths = RuntimePaths.from_environment()
    root = paths.path("Data", "booking-logistics", "discovery")
    sources = sorted(root.glob("*/past-loads.json"))
    if not sources:
        raise ValueError("Prior discovery evidence required")
    source = sources[-1]
    if not company_matches(json.loads(source.with_name("profile.json").read_text())):
        raise PermissionError("Prior company identity not reconciled")
    matches = [row for row in records(json.loads(source.read_text())) if str(row.get("load_id")) == "1752"]
    if len(matches) != 1 or matches[0].get("id") is None:
        raise PermissionError("Owner-selected historical candidate is ambiguous or changed")
    config = CarrierViewConfig.from_environment(CredentialClass.TENANT, SERVICE_REASON)
    if config.base_url != "https://carrierview.com":
        raise PermissionError("Exact owner-verified origin required")
    config.discovery_reads_authorized = True
    config.discovery_provider_id = str(matches[0]["id"])
    prior_details = sorted(paths.path("Data", "booking-logistics", "historical-1752").glob("*/exact-load.json"))
    cached_detail = json.loads(prior_details[-1].read_text()) if prior_details else None
    run_id = utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    paths.path("Data", "booking-logistics", "historical-1752", run_id).mkdir(parents=True, exist_ok=False)
    def persist(kind, payload):
        target = paths.path("Data", "booking-logistics", "historical-1752", run_id, kind + ".json")
        with target.open("x", encoding="utf-8") as output:
            json.dump(payload, output)
    persist("owner-selection", {"booking_reference": "1752", "provider_id": config.discovery_provider_id,
            "owner_reported_completed": True, "credential_class": "tenant",
            "read_only": True, "source_run": source.parent.name, "observed_at": utcnow().isoformat()})
    store = Store(paths.path("Data", "booking-logistics", "carrierview.sqlite3"))
    try:
        contract = ResponseContract(source_reference="Owner-selected historical evidence; UI reconciliation pending",
                                    selectors={})
        async with CarrierViewAdapter(config, contract,
                CarrierViewAudit(store, config.tenant_id, "FreightDesk/Avery")) as adapter:
            try:
                result = await collect_historical(adapter, matches[0], "1752", persist, cached_detail)
            except CarrierViewError as error:
                result = {"booking_reference": "1752", "status": "STOPPED",
                          **error.safe_result(), "imported": False, "live_validated": False}
        persist("sanitized-receipt", result)
        print(json.dumps(result))
    finally:
        store.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        print('{"status":"STOPPED","error_code":"local_evidence_or_configuration_error","imported":false}')
        raise SystemExit(1) from None
