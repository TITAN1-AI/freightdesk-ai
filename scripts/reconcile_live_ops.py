"""Run only through the owner-executed tenant DPAPI launcher after Ascend discovery."""
import asyncio
import json
import os

from pydantic import SecretStr

from app.core.runtime import RuntimePaths
from app.services.carrierview_audit import CarrierViewAudit
from app.services.carrierview_replay_discovery import SERVICE_REASON
from app.services.live_ops import OpsCandidate, TENANT
from app.services.live_ops_carrierview import reconcile_ops, reconciliation_report, validate_reconciliation_scope
from app.services.store import Store
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.config import CarrierViewConfig, CredentialClass
from integrations.carrierview.contract import ResponseContract


async def main():
    manifest_id = input('Exact POC #002 manifest ID to reconcile (no other loads will be read individually): ').strip()
    paths = RuntimePaths.from_environment()
    store = Store(paths.path('Data',TENANT,'operations','operations.sqlite3'))
    try:
        manifest = store.get(TENANT,'ops_manifest',manifest_id)
        candidates = [OpsCandidate.model_validate(r) for r in store.all(TENANT,'ops_candidate')
                      if r['service_date'] == manifest['service_date'] and
                      any(f['source_reference'].startswith(manifest_id+':') for f in r['facts'].values())]
        validate_reconciliation_scope(manifest,candidates)
        with store.transaction():
            grant_id = manifest_id+':carrierview'
            if any(g['id'] == grant_id for g in store.all(TENANT,'ops_read_grant')):
                raise PermissionError('read_attempt_consumed_no_retry')
            store.put(TENANT,'ops_read_grant',grant_id, {'id':grant_id, 'consumed':True,
                'max_gets':3+len(candidates), 'load_numbers':[c.load_number for c in candidates]})
        config = CarrierViewConfig(api_token=SecretStr(os.environ['CARRIERVIEW_TENANT_API_TOKEN']),
            base_url='https://carrierview.com', credential_class=CredentialClass.TENANT,
            elevation_reason=SERVICE_REASON, origin_verified=True, network_reads_authorized=True,
            discovery_reads_authorized=True)
        async with CarrierViewAdapter(config, ResponseContract(source_reference='POC002 bounded discovery', selectors={}),
                                      CarrierViewAudit(store,TENANT,'FreightDesk/Avery')) as adapter:
            tracking = await reconcile_ops(adapter, [c.load_number for c in candidates])
        for number, record in tracking.items():
            store.put(TENANT,'ops_tracking_evidence',manifest_id+':'+number,record)
        report = reconciliation_report(manifest,candidates,tracking)
        store.put(TENANT,'ops_carrierview_reconciliation',manifest_id,report)
        paths.path('Data',TENANT,'operations',manifest_id+'-carrierview-reconciliation.json').write_text(
            json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))

    finally:
        store.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception:
        raise SystemExit('POC002 reconciliation stopped; no raw provider or credential output; do not retry automatically.') from None
