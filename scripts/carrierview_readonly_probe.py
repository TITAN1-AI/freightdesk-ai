"""Run only AFTER owner confirms token storage, origin and bounded live-read authorization."""
import asyncio
import json

from app.core.runtime import RuntimePaths
from app.services.carrierview_audit import CarrierViewAudit
from app.services.carrierview_poc import ReadPlan, stage_readonly_poc
from app.services.store import Store
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.config import CarrierViewConfig, CredentialClass
from integrations.carrierview.contract import ResponseContract


async def main():
    import os
    credential = CredentialClass(os.getenv("CARRIERVIEW_CREDENTIAL_CLASS", "tenant"))
    config = CarrierViewConfig.from_environment(credential, os.getenv("CARRIERVIEW_ELEVATION_REASON"))
    paths = RuntimePaths.from_environment()
    # Both files are runtime-local. A plan contains real identifiers/contacts and must not enter Git.
    contract = ResponseContract.model_validate_json(
        paths.path("Data", "booking-logistics", "carrierview-response-contract.json").read_text(encoding="utf-8-sig"))
    plan = ReadPlan.model_validate_json(
        paths.path("Data", "booking-logistics", "carrierview-read-plan.json").read_text(encoding="utf-8-sig"))
    store = Store(paths.path("Data", "booking-logistics", "carrierview.sqlite3"))
    try:
        async with CarrierViewAdapter(config, contract,
                CarrierViewAudit(store, config.tenant_id, "owner-readonly-probe")) as adapter:
            result = await stage_readonly_poc(adapter, plan, store)
        # Safe receipt only. No provider payload, driver/customer details, URLs or tokens.
        print(json.dumps(result))
    finally:
        store.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        # Pydantic/HTTP exceptions may contain input values: do not print raw tracebacks.
        print("CarrierView probe stopped. Check local configuration and redacted runtime audit. No automatic retry.")
        raise SystemExit(1) from None
