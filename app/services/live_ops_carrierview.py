"""Bounded tenant GET reconciliation for already-discovered POC #002 identities only."""
from app.models.domain import utcnow
from app.services.carrierview_historical import exact_record, records
from app.services.carrierview_replay_discovery import company_matches
from app.services.live_ops import TrackingEvidence
from integrations.carrierview.schemas import aware_timestamp


async def reconcile_ops(adapter, load_numbers, *, filters=('active','past')):
    if filters not in {('active','past'),('active','future')}:
        raise ValueError('bounded_documented_filters_required')
    if not 0 < len(load_numbers) <= 30 or len(set(load_numbers)) != len(load_numbers):
        raise ValueError('bounded_unique_ops_identities_required')
    if adapter.config.credential_class.value != 'tenant':
        raise PermissionError('tenant_service_credential_required_no_fallback')
    profile, _ = await adapter._request('GET','/api/profile','profile_discovery', discovery=True)
    if not company_matches(profile):
        raise PermissionError('tenant_company_identity_not_verified')
    indexed = {number:{} for number in load_numbers}
    for filter_name in filters:
        operation = {'active':'loads_discovery','past':'past_loads_discovery','future':'future_loads_discovery'}[filter_name]
        raw, _ = await adapter._request('GET','/api/loads', operation, params={'filter':filter_name}, discovery=True)
        rows = records(raw)
        if len(rows) > 2000:
            raise ValueError('bounded_list_count_exceeded')
        for row in rows:
            number = str(row.get('load_id',''))
            if number in indexed and row.get('id') is not None:
                indexed[number].setdefault(adapter.provider_id(row['id']), set()).add(filter_name)
        del raw, rows  # No raw list persisted; unmatched customer records are discarded.
    result = {}
    for number, ids in indexed.items():
        if not ids:
            result[number] = TrackingEvidence(load_number=number, existence='NOT_FOUND_IN_BOUNDED_READ',
                observed_at=utcnow(), source_reference='tenant:bounded-'+ '-and-'.join(filters)+'-lists;pagination-unverified')
            continue
        if len(ids) != 1:
            result[number] = TrackingEvidence(load_number=number, existence='DUPLICATE', provider_ids=list(ids),
                observed_at=utcnow(), source_reference='tenant:bounded-list-identity-conflict')
            continue
        provider_id = next(iter(ids))
        adapter.config.discovery_provider_id = provider_id
        raw, _ = await adapter._request('GET', '/api/loads/'+provider_id, 'exact_load_discovery', discovery=True)
        detail = exact_record(raw, provider_id, number)
        position = detail.get('last_position')
        stamp = aware_timestamp(position.get('timestamp')) if isinstance(position, dict) else None
        # Existence and timestamp presence are established here; app/route/status meanings are not
        # automatically promoted to verified operational semantics from a historical replay.
        result[number] = TrackingEvidence(load_number=number, existence='EXISTS', provider_ids=[provider_id],
            observed_list_filters=sorted(ids[provider_id]),
            integration_kind='NATIVE_CARRIERVIEW' if detail.get('integration_type') == 'carrier_view' else 'UNKNOWN',
            observed_at=utcnow(), last_position_at=stamp, last_position_available=bool(position) if position is not None else None,
            semantics_verified=False, source_reference='tenant:exact-load:'+provider_id,
            provider_flags={k:detail[k] for k in ('route_started','driver_is_late','delivery_arrived','delivery_departed')
                            if isinstance(detail.get(k), bool)})
        del raw, detail
    return result


PICKUPS = {'1755','1756','1757','1758','1759','1762','1768','1769'}
DELIVERIES = {'1761','1766','1767'}
MANIFEST_ID = 'owner-active-loads-20260911-02'


def validate_reconciliation_scope(manifest, candidates):
    from app.services.live_ops import require_fresh_reconciled_active_manifest
    require_fresh_reconciled_active_manifest(manifest)
    if (manifest['id'] != MANIFEST_ID or manifest['service_date'] != '2026-09-11' or
            {r['load_number'] for r in manifest['PICKUP_TRACKING_QUEUE']} != PICKUPS or
            {r['load_number'] for r in manifest['DELIVERY_WATCH_QUEUE']} != DELIVERIES or
            len(manifest['PICKUP_TRACKING_QUEUE']) != 8 or len(manifest['DELIVERY_WATCH_QUEUE']) != 3 or
            len(candidates) != 11 or {c.load_number for c in candidates} != PICKUPS | DELIVERIES or
            any(c.service_date.isoformat() != '2026-09-11' or c.pickup_due != (c.load_number in PICKUPS) or
                c.delivery_due != (c.load_number in DELIVERIES) or not c.identity_verified for c in candidates)):
        raise PermissionError('owner_reconciled_exact_eleven_load_scope_required')


def reconciliation_report(manifest, candidates, tracking):
    """No private field values or tracking URLs; missing-list evidence never authorizes creation."""
    from app.services.live_ops import delivery_classification, tracking_inputs
    validate_reconciliation_scope(manifest,candidates)
    if set(tracking) != PICKUPS | DELIVERIES:
        raise ValueError('reconciliation_result_scope_mismatch')
    now = utcnow()
    pickups, deliveries = [], []
    for c in sorted(candidates,key=lambda c:int(c.load_number)):
        t=tracking[c.load_number]
        if t.load_number != c.load_number:
            raise ValueError('reconciliation_result_identity_mismatch')
        result = 'NOT_FOUND_IN_BOUNDED_SEARCH' if t.existence == 'NOT_FOUND_IN_BOUNDED_READ' else t.existence
        base = {'load_id':c.load_number,'carrierview_result':result,'provider_ids':t.provider_ids,
                'observed_list_filters':t.observed_list_filters,'provider_state':'UNKNOWN',
                'integration_type':t.integration_kind,'last_position_available':t.last_position_available,
                'arrival_departure_flags':{k:v for k,v in t.provider_flags.items() if k in {'delivery_arrived','delivery_departed'}}}
        if c.pickup_due:
            _,missing=tracking_inputs(c)
            classification='MISSING_REQUIRED_DATA' if missing else 'NEEDS_REVIEW'
            if t.existence == 'EXISTS':
                classification=('ALREADY_TRACKING' if t.semantics_verified and t.tracking_active is True else
                    'CARRIERVIEW_RECORD_EXISTS_NOT_ACTIVE' if t.semantics_verified and t.tracking_active is False else 'NEEDS_REVIEW')
            if t.existence == 'DUPLICATE':
                classification='NEEDS_REVIEW'
            pickups.append(base | {'classification':classification,'required_data_complete':not missing,
                'missing_required_facts':missing,'creation_blocked_by_existing_record':t.existence in {'EXISTS','DUPLICATE'},
                'next_action':'DO_NOT_CREATE_EXISTING_RECORD' if t.existence in {'EXISTS','DUPLICATE'} else
                              'VERIFY_EXISTENCE_AND_REQUIRED_FACTS_BEFORE_PILOT_REVIEW'})
        if c.delivery_due:
            classification,_=delivery_classification(c,t,now)
            if classification not in {'TRACKING_ACTIVE','TRACKING_STALE','EN_ROUTE_DELIVERY','CHECKED_IN_DELIVERY','DELIVERED'}:
                classification='UNKNOWN'
            age=(now-t.last_position_at).total_seconds() if t.last_position_at else None
            deliveries.append(base | {'classification':classification,'position_age_seconds':age if age is not None and age>=0 else None,
                'freshness':'TIMESTAMP_AGE_ONLY' if age is not None and age>=0 else 'UNKNOWN',
                'next_action':'REVIEW_PROVIDER_STATE_AND_DELIVERY_EVIDENCE','pod_status':'UNKNOWN'})
    return {'manifest_id':manifest['id'],'service_date':manifest['service_date'],
        'ascend_evidence_hash':manifest['immutable_evidence_hash'],'ascend_observed_at':manifest['observed_at'],
        'calculated_at':now.isoformat(),'actor':'FreightDesk/Avery','credential_class':'tenant',
        'pickups':pickups,'deliveries':deliveries,'proposed_pilot':None,
        'pilot_reason':'Bounded lists do not prove record absence; complete verified phone/stop facts are required.',
        'future_approval_action':'Create exactly one native CarrierView shipment only after identity, verified absence, phone, complete stops and communication effects are reconciled.',
        'production_writes':False,'canonical_mutation':False,'live_validated':False}
