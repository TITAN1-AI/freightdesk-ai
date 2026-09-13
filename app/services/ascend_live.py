"""Private Ascend read ledger and projections, separate from canonical/mail/history writes."""
import json
import sqlite3

from app.core.config import ROOT
from app.core.runtime import RuntimePaths
from app.models.domain import AuditEvent, utcnow
from app.policies.engine import PolicyEngine
from app.services.ascend_reconciliation import reconcile
from app.services.mail_sync import digest
from app.services.mail_view import sanitized
from app.services.store import Store
from executors.playwright.browser import AveryBrowserSession, BrowserExecutor
from integrations.ascend.adapter import AscendBrowserAdapter, normalize_field
from integrations.ascend.models import PRIVATE_FIELDS, AscendError, BrowserContract, ComparisonEvidence, ReadGrant

TENANT = 'booking-logistics'


def local_records(path, kind, load_number=None, identity_key=None):
    if not path.exists():
        return []
    with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
        sql = 'SELECT body FROM records WHERE tenant=? AND kind=?'
        args = [TENANT, kind]
        if load_number is not None:
            if identity_key not in {'booking_load_id', 'source_load_id'}:
                raise ValueError('invalid_local_identity_key')
            sql += ' AND json_extract(body, ?) = ?'
            args += ['$.'+identity_key, load_number]
        return [json.loads(row[0]) for row in db.execute(sql, args)]


def existing_evidence(paths, load_number):
    result = []
    history = local_records(paths.path('Data', TENANT, 'history', 'history.sqlite3'),
                            'ascend_history_record', load_number, 'source_load_id')
    for row in history:
        data = row['data']
        fields = {'load_number':row['source_load_id'], 'customer':data['raw_customer'],
            'carrier':data['raw_carrier'], 'carrier_mc':data['carrier_mc'], 'carrier_dot':data['carrier_dot'],
            'equipment':data['raw_equipment'], 'commodity':data['commodity'], 'weight':data['weight'],
            'status':data['load_status'], 'customer_revenue':data['historical_total_income'],
            'total_expenses':data['historical_total_expenses'], 'gross_profit':data['historical_gross_profit_loss'],
            'gross_margin':data['historical_margin_percent'], 'notes':data['notes'], 'private_notes':data['private_notes']}
        result.append(ComparisonEvidence(source='Ascend history', load_number=load_number,
            identity_reconciled=True, observed_at=row['provenance']['committed_at'],
            evidence_reference=row['id'], fields=fields))
    canonical = local_records(paths.path('Data', TENANT, 'carrierview.sqlite3'),
                              'shipment', load_number, 'booking_load_id')
    for row in canonical:
        fields = {'load_number':load_number, 'status':row.get('status'),
            'customer_reference':row.get('customer_reference'),
            'pickup_appointment':row['origin'].get('appointment'),
            'delivery_appointment':row['destination'].get('appointment'),
            'origin':row['origin'].get('location'), 'destination':row['destination'].get('location')}
        stamp = row.get('tracking', {}).get('verified_at')
        result.append(ComparisonEvidence(source='canonical', load_number=load_number,
            identity_reconciled=True, observed_at=stamp, evidence_reference=row['id'], fields=fields))
        # Only explicitly recorded raw provider fields, never canonical-derived status, qualify as CarrierView evidence.
        raw = row.get('tracking', {}).get('provider_metadata', {}).get('raw_load', {})
        if raw and row.get('provider_metadata', {}).get('historical_replay', {}).get('owner_reconciliation'):
            cv_fields = {'load_number':load_number}
            for stop in raw.get('locations', []):
                if stop.get('type') in {'pickup','delivery'}:
                    key = 'origin' if stop['type'] == 'pickup' else 'destination'
                    cv_fields[key] = stop.get('address')
            for stop in row['provider_metadata']['historical_replay'].get('report', {}).get('stops', []):
                if stop.get('kind') in {'pickup','delivery'}:
                    cv_fields[stop['kind']+'_appointment'] = stop.get('appointment_start')
            # Only previously owner-reconciled stop mappings are reused; no invented status or driver mapping.
            result.append(ComparisonEvidence(source='CarrierView', load_number=load_number,
                identity_reconciled=True, observed_at=stamp,
                evidence_reference='cached-carrierview:'+row['carrierview_load_id'], fields=cv_fields))
    # Outlook has no explicit real shipment-correlation evidence. Do not inspect unrelated messages or infer a match.
    for source in result:
        source.fields = {key: normalize_field(key, value, 'local evidence', source.source, utcnow()).normalized
                         for key, value in source.fields.items()}
    return result


def projected_summary(paths=None):
    paths = paths or RuntimePaths.from_environment()
    path = paths.path('Data', TENANT, 'ascend.sqlite3')
    connections = local_records(path, 'ascend_connection')
    observations = sorted(local_records(path, 'ascend_observation'), key=lambda o:o['observed_at'], reverse=True)
    actions = local_records(path, 'ascend_action')
    audit = []
    if path.exists():
        with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
            audit = [json.loads(row[0]) for row in db.execute(
                'SELECT body FROM audit WHERE tenant=? ORDER BY seq DESC LIMIT 30', (TENANT,))]
    rows = []
    for o in observations[:1]:
        rows.append({'load_number':o['load_number'], 'observed_at':o['observed_at'],
            'provider_facts':[{key: value for key, value in fact.items() if key not in {'raw_value','normalized'}} |
                {'display_value':'[private field retained locally]' if field in PRIVATE_FIELDS else
                 sanitized(fact['normalized']), 'raw_display':'[private field retained locally]' if field in PRIVATE_FIELDS else
                 sanitized(fact['raw_value'])} for field, fact in o['fields'].items()],
            'reconciliation':o.get('reconciliation', []),
            'source_separation':['AscendTMS provider facts', 'canonical', 'CarrierView', 'Outlook', 'Ascend history',
                                 'FreightDesk-derived reconciliation']})
    return {'connection':connections[0] if connections else {'status':'NOT_AUTHENTICATED',
        'executor_status':'STOPPED', 'last_verified_company':None, 'last_successful_read':None},
        'loads':rows, 'pending_approvals':[{'id':a['id'], 'operation':a['operation'], 'state':a['state']}
            for a in actions if a['state'] in {'AWAITING_APPROVAL','APPROVED','QUEUED','UNCERTAIN','EXECUTING'}],
        'audit':[{'event':a['event'], 'timestamp':a['timestamp'], 'facts':a['facts']} for a in audit],
        'live_validated':False, 'production_writes':'BLOCKED', 'browser_activity':'No browser is launched by this view'}


async def bounded_read(contract: BrowserContract, grant: ReadGrant, *, paths=None):
    paths = paths or RuntimePaths.from_environment()
    if grant.expires_at <= utcnow() or grant.contract_hash != digest(contract.model_dump(mode='json')):
        raise AscendError('invalid_read_grant')
    if not contract.verified or not contract.verified_at or contract.verified_by != 'owner':
        raise AscendError('unverified_dom_contract')
    policies = PolicyEngine(ROOT/'config'/'policies.json')
    store = Store(paths.path('Data', TENANT, 'ascend.sqlite3'))
    browser = AveryBrowserSession(paths)
    if contract.tenant_identity_source == 'OWNER_ATTESTED':
        from integrations.ascend.identity import OwnerAttestedIdentity
        attestation = OwnerAttestedIdentity(owner_authorized=True)
        if str(browser.profile).rstrip('\\/').lower() != attestation.profile.lower() or grant.load_number != '1752':
            store.close()
            raise AscendError('owner_attested_profile_or_load_mismatch')
    connections = store.all(TENANT, 'ascend_connection')
    last_connection = connections[0] if connections else {
        'last_verified_company':None, 'last_successful_read':None}
    def running():
        controls = store.all(TENANT, 'ascend_controls')
        return not any(c.get('paused', True) or c.get('human_takeover', True) for c in controls)
    try:
        if not running():
            raise AscendError('ascend_paused_or_takeover')
        with store.transaction():
            if any(g['id'] == grant.id for g in store.all(TENANT, 'ascend_read_grant')):
                raise AscendError('read_grant_already_consumed_no_retry')
            store.put(TENANT, 'ascend_read_grant', grant.id, {**grant.model_dump(mode='json'), 'consumed':True})
            store.put(TENANT, 'ascend_connection', 'current', {**last_connection, 'status':'READING',
                'executor_status':'STARTING'})
        context = await browser.launch(owner_authorized=True, require_existing=True)
        await browser.readonly_network(contract.origin.rstrip('/'))
        page = context.pages[0]
        adapter = AscendBrowserAdapter(BrowserExecutor(page), contract, policies, running)
        observation = await adapter.read_load(grant)
        previous = store.all(TENANT, 'ascend_observation')
        observation.session_reuse_proven = bool(observation.account_hash) and any(o['account_hash'] == observation.account_hash and
                                               o['contract_hash'] == observation.contract_hash for o in previous)
        comparisons = reconcile(observation, existing_evidence(paths, grant.load_number))
        with store.transaction():
            store.put(TENANT, 'ascend_observation', grant.id,
                      {**observation.model_dump(mode='json'), 'reconciliation':comparisons})
            store.put(TENANT, 'ascend_connection', 'current', {'status':'READ_COMPLETE',
                'executor_status':'STOPPED_AFTER_BOUNDED_READ',
                'last_verified_company':observation.company if observation.provider_tenant_identity_verified else None,
                'tenant_identity':observation.tenant_identity,
                'tenant_identity_source':observation.tenant_identity_source,
                'provider_tenant_identity_verified':observation.provider_tenant_identity_verified,
                'session_authenticated':observation.session_authenticated,
                'last_successful_read':observation.observed_at.isoformat(),
                'session_reuse_proven':observation.session_reuse_proven})
            store.audit(AuditEvent(tenant_id=TENANT, actor_id='FreightDesk/Avery', source='AscendTMS',
                event='ASCEND_BOUNDED_READ_COMPLETE', explanation='Exact owner-selected load read; no canonical mutation',
                facts={'session_class':observation.session_class, 'grant_id':grant.id,
                       'tenant_identity_source':observation.tenant_identity_source,
                       'contract_hash':grant.contract_hash, 'observation_hash':observation.version}))
        return projected_summary(paths)
    except Exception:
        with store.transaction():
            store.put(TENANT, 'ascend_connection', 'current', {**last_connection, 'status':'REVIEW_REQUIRED',
                'executor_status':'STOPPED_NO_RETRY'})
            store.audit(AuditEvent(tenant_id=TENANT, actor_id='FreightDesk/Avery', source='AscendTMS',
                event='ASCEND_READ_STOPPED', explanation='Read stopped; no raw browser error retained',
                facts={'session_class':'Avery operational browser session', 'grant_id':grant.id}))
        raise AscendError('bounded_read_stopped_owner_review_required') from None
    finally:
        try:
            await browser.close()
        finally:
            store.close()
