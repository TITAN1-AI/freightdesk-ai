"""One tenant profile GET, then one past-load GET only after exact company match."""
import asyncio
import json

from app.core.runtime import RuntimePaths
from app.models.domain import utcnow
from app.services.carrierview_audit import CarrierViewAudit
from app.services.carrierview_replay_discovery import SERVICE_REASON, discover_past
from app.services.store import Store
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.config import CarrierViewConfig, CredentialClass
from integrations.carrierview.contract import ResponseContract
from integrations.carrierview.errors import CarrierViewError


async def main():
    config = CarrierViewConfig.from_environment(CredentialClass.TENANT, SERVICE_REASON)
    if config.base_url != "https://carrierview.com":
        raise PermissionError("Exact owner-verified origin required")
    config.discovery_reads_authorized = True
    paths = RuntimePaths.from_environment().ensure()
    run_id = utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    paths.path("Data", "booking-logistics", "discovery", run_id).mkdir(parents=True, exist_ok=False)
    def persist(kind, payload):
        path = paths.path("Data", "booking-logistics", "discovery", run_id, kind + ".json")
        with path.open("x", encoding="utf-8") as output:
            json.dump(payload, output)
    with paths.path("Data", "booking-logistics", "carrierview-service-config.json").open(
            "w", encoding="utf-8") as output:
        json.dump({"credential_class": "tenant", "agent_api_available": False,
                   "executed_by": "FreightDesk/Avery", "elevation_reason": SERVICE_REASON,
                   "base_url": config.base_url, "origin_verified": True,
                   "writes_authorized": False}, output)
    store = Store(paths.path("Data", "booking-logistics", "carrierview.sqlite3"))
    try:
        audit = CarrierViewAudit(store, config.tenant_id, "FreightDesk/Avery")
        contract = ResponseContract(source_reference="Owner-authorized tenant historical discovery", selectors={})
        async with CarrierViewAdapter(config, contract, audit) as adapter:
            try:
                result = await discover_past(adapter, persist)
            except CarrierViewError as error:
                result = {"credential_class": "tenant", "status": "STOPPED",
                          **error.safe_result(), "imported": False, "live_validated": False}
        persist("sanitized-receipt", result)
        print(json.dumps(result))
    finally:
        store.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        print('{"status":"STOPPED","error_code":"local_configuration_or_mapping_error","imported":false}')
        raise SystemExit(1) from None
