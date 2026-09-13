"""One owner-authorized agent-only discovery run: two GETs, no import or retries."""
import asyncio
import json

from app.core.runtime import RuntimePaths
from app.models.domain import utcnow
from app.services.carrierview_audit import CarrierViewAudit
from app.services.carrierview_discovery import discover_candidates
from app.services.store import Store
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.config import CarrierViewConfig, CredentialClass
from integrations.carrierview.contract import ResponseContract
from integrations.carrierview.errors import CarrierViewError


async def main():
    config = CarrierViewConfig.from_environment(CredentialClass.AGENT)
    if config.base_url != "https://carrierview.com":
        raise PermissionError("Discovery requires the exact owner-verified origin")
    config.discovery_reads_authorized = True
    paths = RuntimePaths.from_environment().ensure()
    run_id = utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    directory = paths.path("Data", "booking-logistics", "discovery", run_id)
    directory.mkdir(parents=True, exist_ok=False)
    # Persist no credentials, headers or raw payloads in logs/source. Private evidence is runtime-only.
    def persist(kind, envelope):
        target = paths.path("Data", "booking-logistics", "discovery", run_id, kind + ".json")
        with target.open("x", encoding="utf-8") as output:
            json.dump(envelope, output)

    with paths.path("Data", "booking-logistics", "carrierview-discovery-config.json").open(
            "w", encoding="utf-8") as output:
        json.dump({"base_url": config.base_url, "origin_verified": config.origin_verified,
                   "scope": ["GET /api/profile", "GET /api/loads?filter=active"],
                   "credential_class": "agent", "authorized_run": run_id}, output)
    store = Store(paths.path("Data", "booking-logistics", "carrierview.sqlite3"))
    try:
        contract = ResponseContract(source_reference="Owner-authorized envelope discovery; mapping unverified",
                                    selectors={}, verified_for_network=False)
        async with CarrierViewAdapter(config, contract,
                CarrierViewAudit(store, config.tenant_id, "owner-authorized-discovery")) as adapter:
            try:
                result = await discover_candidates(adapter, persist)
            except CarrierViewError as error:
                result = {"credential_class": "agent", "status": "STOPPED", **error.safe_result(),
                          "imported": False, "live_validated": False}
        # The receipt contains only allowlisted identifiers and safe status, never raw errors.
        persist("sanitized-receipt", result)
        print(json.dumps(result))
    finally:
        store.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        print('{"status":"STOPPED","error_code":"local_configuration_or_storage_error","imported":false}')
        raise SystemExit(1) from None
