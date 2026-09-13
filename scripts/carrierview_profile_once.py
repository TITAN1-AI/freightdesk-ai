"""Explicit owner-authorized single agent profile GET; no retries or other requests."""
import asyncio
import json

from app.core.runtime import RuntimePaths
from app.services.carrierview_audit import CarrierViewAudit
from app.services.store import Store
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.config import CarrierViewConfig, CredentialClass
from integrations.carrierview.contract import ResponseContract
from integrations.carrierview.errors import CarrierViewError


async def main():
    config = CarrierViewConfig.from_environment(CredentialClass.AGENT)
    if config.base_url != "https://carrierview.com":
        raise PermissionError("Exact owner-verified origin required")
    config.discovery_reads_authorized = True
    paths = RuntimePaths.from_environment()
    store = Store(paths.path("Data", "booking-logistics", "carrierview.sqlite3"))
    try:
        contract = ResponseContract(source_reference="Owner authorized one profile GET only", selectors={})
        async with CarrierViewAdapter(config, contract,
                CarrierViewAudit(store, config.tenant_id, "owner-profile-eligibility-check")) as adapter:
            try:
                await adapter._request("GET", "/api/profile", "profile_discovery", discovery=True)
                result = {"success": True, "error_code": None}
            except CarrierViewError as error:
                result = {"success": False, "error_code": error.code}
        print(json.dumps(result))
    finally:
        store.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        print('{"success":false,"error_code":null}')
        raise SystemExit(1) from None
