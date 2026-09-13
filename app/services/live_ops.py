"""POC #002 planning only. Provider facts, derived queues and proposed writes stay separate."""
import re
from datetime import date, timedelta
from typing import Literal

from pydantic import AwareDatetime, Field

from app.models.domain import AuditEvent, Model, utcnow
from app.services.action_ledger import payload_hash
from app.services.mail_view import sanitized
from app.services.store import Store
from integrations.carrierview.schemas import CreateLocation, CreateTrackingLoad, aware_timestamp

TENANT = 'booking-logistics'


class OpsReadGrant(Model):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')
    service_date: date
    board_date_format: Literal['ISO', 'US'] = 'ISO'
    owner_authorized: Literal[True] = True
    maximum_candidates: Literal[30] = 30
    maximum_board_rows: Literal[500] = 500
    consumed: Literal[True] = True


class OpsFact(Model):
    value: str | None = Field(default=None, repr=False)
    source: Literal['AscendTMS', 'CarrierView', 'OWNER_ATTESTED']
    observed_at: AwareDatetime = Field(default_factory=utcnow)
    source_reference: str
    verified: bool = False


class OpsCandidate(Model):
    load_number: str = Field(pattern=r'^\d{1,20}$')
    service_date: date
    pickup_due: bool = False
    delivery_due: bool = False
    facts: dict[str, OpsFact] = Field(default_factory=dict, repr=False)
    identity_verified: bool = False
    notes_present: bool | None = None
    additional_stops_verified: bool = False
    stops: list[dict] = Field(default_factory=list, repr=False)


class TrackingEvidence(Model):
    load_number: str
    existence: Literal['EXISTS', 'ABSENT_VERIFIED', 'NOT_FOUND_IN_BOUNDED_READ', 'UNKNOWN', 'DUPLICATE'] = 'UNKNOWN'
    provider_ids: list[str] = Field(default_factory=list)
    observed_at: AwareDatetime | None = None
    last_position_at: AwareDatetime | None = None
    last_position_available: bool | None = None
    tracking_active: bool | None = None
    delivered: bool | None = None
    delivery_arrived: bool | None = None
    eta: AwareDatetime | None = None
    provider_risk: bool | None = None
    semantics_verified: bool = False
    source_reference: str | None = None
    provider_flags: dict[str, bool | None] = Field(default_factory=dict)
    observed_list_filters: list[Literal['active','past','future']] = Field(default_factory=list)
    integration_kind: Literal['NATIVE_CARRIERVIEW','UNKNOWN'] = 'UNKNOWN'


def value(candidate, key):
    fact = candidate.facts.get(key)
    return fact.value if fact and fact.verified and fact.source == 'AscendTMS' else None


def tracking_inputs(candidate):
    missing = []
    phone = value(candidate, 'driver_phone')
    phone_fact = candidate.facts.get('driver_phone')
    if not phone_fact or not phone_fact.verified:
        missing.append('driver_phone_not_observed_or_unverified')
    elif phone and not re.fullmatch(r'\+[1-9]\d{7,14}', phone):
        missing.append('driver_phone_format_requires_review')
    elif not phone:
        missing.append('verified_E164_driver_phone')
    if not candidate.identity_verified:
        missing.append('exact_load_identity')
    if not candidate.additional_stops_verified:
        missing.append('complete_stop_sequence')
    if len(candidate.stops) < 2:
        missing.append('pickup_and_delivery_stops')
    types = set()
    locations = []
    for stop in candidate.stops:
        types.add(stop.get('type'))
        if not stop.get('verified') or not all(stop.get(k) for k in ('address','company','dateFrom','dateTo')):
            missing.append('verified_stop_address_company_window')
            continue
        start, end = aware_timestamp(stop['dateFrom']), aware_timestamp(stop['dateTo'])
        if not start or not end or start > end:
            missing.append('verified_stop_timezone_and_window')
            continue
        try:
            locations.append(CreateLocation(type=stop['type'], address=stop['address'],
                dateFrom=stop['dateFrom'], dateTo=stop['dateTo']))
        except ValueError:
            missing.append('supported_stop_type')
    if not {'pickup','destination'} <= types:
        missing.append('pickup_and_delivery_stops')
    if missing:
        return None, sorted(set(missing))
    return CreateTrackingLoad(load_id=candidate.load_number, driver_phone=phone, locations=locations), []


def pickup_classification(candidate, tracking, now=None):
    now = now or utcnow()
    payload, missing = tracking_inputs(candidate)
    if candidate.load_number == '1760':
        return 'NEEDS_REVIEW', ['owner_reports_delivered_reconcile_provider_before_tracking'], None
    if any(f.verified and (f.observed_at > now or now-f.observed_at > timedelta(hours=4)) for f in candidate.facts.values()):
        return 'NEEDS_REVIEW', ['refresh_stale_ascend_facts'], None
    if tracking.existence == 'DUPLICATE':
        return 'NEEDS_REVIEW', ['duplicate_tracking_identity'], None
    if tracking.existence == 'EXISTS':
        return ('ALREADY_TRACKING' if tracking.tracking_active is True and tracking.semantics_verified else
                'NEEDS_REVIEW'), ['existing_tracking_load_do_not_create'], None
    if 'verified_E164_driver_phone' in missing:
        return 'MISSING_DRIVER_PHONE', missing, None
    if any(key.startswith('driver_phone_') for key in missing):
        return 'NEEDS_REVIEW', missing, None
    if missing:
        return 'MISSING_REQUIRED_STOP_DATA', missing, None
    if (tracking.existence != 'ABSENT_VERIFIED' or not tracking.observed_at or
            not timedelta(0) <= now-tracking.observed_at <= timedelta(minutes=15)):
        return 'NEEDS_REVIEW', ['tracking_absence_not_freshly_verified'], None
    return 'READY_FOR_TRACKING', [], payload


def delivery_classification(candidate, tracking, now=None):
    now = now or utcnow()
    # CarrierView fields with unverified semantics or old snapshots are not live status proof.
    fresh = tracking.observed_at and timedelta(0) <= now-tracking.observed_at <= timedelta(minutes=15)
    if not fresh or not tracking.semantics_verified or tracking.existence != 'EXISTS':
        return 'UNKNOWN', 'REVIEW'
    if tracking.delivered is True:
        return 'DELIVERED', 'REVIEW POD REQUIREMENT'
    if tracking.delivery_arrived is True:
        return 'CHECKED_IN_DELIVERY', 'REVIEW'
    if tracking.provider_risk is True:
        return 'ETA_AT_RISK', 'REVIEW'
    if tracking.last_position_at and (tracking.last_position_at > now or now-tracking.last_position_at > timedelta(minutes=60)):
        return 'TRACKING_STALE', 'TRACKING STALE'
    if tracking.tracking_active is True and tracking.last_position_at:
        return 'TRACKING_ACTIVE', 'REVIEW ETA / APPOINTMENT'
    return 'UNKNOWN', 'REVIEW'


class OpsActionLedger:
    """Durable proposals only, separate from canonical shipments. No dispatch/approve method."""
    def __init__(self, store: Store):
        self.store = store

    def propose(self, manifest_id, candidate, payload):
        body = payload.model_dump(exclude_none=True)
        fingerprint = payload_hash(body)
        action_id = 'ops-'+payload_hash({'load':candidate.load_number, 'payload':fingerprint})[:24]
        action = {'id':action_id, 'tenant_id':TENANT, 'manifest_id':manifest_id,
            'load_number':candidate.load_number, 'actor':'FreightDesk/Avery', 'credential_class':'tenant',
            'method':'POST', 'path':'/api/loads', 'payload':body, 'payload_hash':fingerprint,
            'state':'AWAITING_OWNER_REVIEW', 'attempts':0, 'created_at':utcnow().isoformat(),
            'source_evidence_hash':payload_hash(candidate.model_dump(mode='json')),
            'unresolved_contract_fields':['stop company wire mapping', 'creation SMS/welcome/tracking side effects'],
            'pre_dispatch_requirements':['fresh duplicate check', 'exact one-load owner approval',
                'verified company wire mapping', 'documented communication effects disclosed and authorized',
                'production transport remains disabled until separately implemented/authorized'],
            'canonical_mutation':False}
        with self.store.transaction():
            prior = [a for a in self.store.all(TENANT, 'ops_proposed_action') if a['load_number'] == candidate.load_number]
            if prior:
                if any(a['payload_hash'] != fingerprint for a in prior):
                    raise ValueError('changed_payload_requires_reconciliation_no_duplicate_proposal')
                return prior[0]
            self.store.put(TENANT, 'ops_proposed_action', action_id, action)
            self.store.audit(AuditEvent(tenant_id=TENANT, actor_id='FreightDesk/Avery', source='POC002',
                event='TRACKING_PAYLOAD_PROPOSED', explanation='Proposal only; no provider execution or canonical mutation',
                facts={'load_number':candidate.load_number, 'payload_hash':fingerprint, 'action_id':action_id}))
        return action


def build_manifest(manifest_id, service_date, candidates, tracking, *, ledger=None, coverage='PARTIAL', now=None,
                   source_view='Active Loads', board_row_count=None, evidence_hash=None, cross_check=None):
    now = now or utcnow()
    pickups, deliveries, actions = [], [], []
    counts = {n:sum(c.load_number == n for c in candidates) for n in {c.load_number for c in candidates}}
    for candidate in candidates:
        if candidate.service_date != service_date or counts[candidate.load_number] != 1:
            raise ValueError('manifest_scope_or_load_identity_conflict')
        cv = tracking.get(candidate.load_number, TrackingEvidence(load_number=candidate.load_number))
        if cv.load_number != candidate.load_number:
            raise ValueError('tracking_load_identity_mismatch')
        if candidate.pickup_due:
            status, missing, payload = pickup_classification(candidate, cv, now)
            pickups.append({'load_number':candidate.load_number, 'classification':status, 'missing':missing,
                'provider_ids':cv.provider_ids, 'tracking_existence':cv.existence,
                'ascend_status':sanitized(value(candidate,'status')), 'provider_flags':cv.provider_flags})
            if payload and ledger:
                action = ledger.propose(manifest_id, candidate, payload)
                actions.append({k:action[k] for k in ('id','load_number','payload_hash','state','unresolved_contract_fields')})
        if candidate.delivery_due:
            status, action = delivery_classification(candidate, cv, now)
            deliveries.append({'load_number':candidate.load_number, 'delivery_appointment':sanitized(value(candidate,'delivery_appointment')),
                'classification':status, 'next_action':action, 'tracking_existence':cv.existence,
                'ascend_status':sanitized(value(candidate,'status')), 'provider_flags':cv.provider_flags,
                'provider_ids':cv.provider_ids, 'last_position_available':cv.last_position_available,
                'latest_tracking_timestamp':cv.last_position_at.isoformat() if cv.last_position_at else None,
                'eta':cv.eta.isoformat() if cv.semantics_verified and cv.eta else None})
    complete_pilots = [c for c in candidates if len(c.stops) == 2 and
                       any(a['load_number'] == c.load_number for a in actions)]
    pilot = min(complete_pilots, key=lambda c:int(c.load_number)).load_number if complete_pilots else None
    pickup_count, delivery_count = len(pickups), len(deliveries)
    reconciled = source_view == 'Active Loads' and pickup_count == 8 and delivery_count == 3
    return {'id':manifest_id, 'title':'POC #002 — LIVE OPERATIONS', 'service_date':service_date.isoformat(),
        'calculated_at':now.isoformat(), 'raw_vs_derived':'FreightDesk-derived queues; provider facts stored separately',
        'observed_at':now.isoformat(), 'source_view':source_view, 'board_row_count':board_row_count,
        'immutable_evidence_hash':evidence_hash, 'source_coverage':coverage,
        'reconciliation_status':'OPS_BOARD_RECONCILED' if reconciled else 'OPS_BOARD_MISMATCH',
        'PICKUP_TRACKING_QUEUE':pickups, 'DELIVERY_WATCH_QUEUE':deliveries,
        'expected_pickups':8, 'expected_deliveries':3,
        'pickup_count_difference':pickup_count-8, 'delivery_count_difference':delivery_count-3,
        'NON_ACTIVE_SERVICE_DATE_RECORDS': (cross_check or {}).get('NON_ACTIVE_SERVICE_DATE_RECORDS', []),
        'active_loads_missing_from_all_loads': (cross_check or {}).get('active_loads_missing_from_all_loads', []),
        'proposed_actions':actions, 'proposed_pilot':pilot,
        'pilot_authorization_ready':False, 'production_writes':'BLOCKED', 'communications':'BLOCKED',
        'owner_reported_delivered_load':'1760', 'owner_report_is_provider_fact':False, 'live_validated':False}


def owner_report(manifest):
    def cell(raw):
        text = sanitized(str(raw)) if raw is not None else 'UNKNOWN'
        return text.replace('|', '\\|').replace('\n',' ').replace('<','&lt;').replace('>','&gt;')
    lines = ['# POC #002 — LIVE OPERATIONS', '', 'Operating date: '+manifest['service_date'],
        'Source view: '+manifest.get('source_view','UNKNOWN')+'. Coverage: '+manifest['source_coverage']+'. Counts are observations, not forced targets.',
        'Reconciliation: '+manifest.get('reconciliation_status','OPS_BOARD_MISMATCH')+'.',
        'Generated: '+manifest['calculated_at'], '',
        '## PICKUP_TRACKING_QUEUE', '', '| Load | Classification | CarrierView existence | Missing / review |',
        '|---|---|---|---|']
    for row in manifest['PICKUP_TRACKING_QUEUE']:
        lines.append('| '+' | '.join(cell(row[key]) for key in ('load_number','classification','tracking_existence'))+
                     ' | '+cell(', '.join(row['missing']))+' |')
    lines.extend(['', '## DELIVERY_WATCH_QUEUE', '',
        '| Load | Appointment | Ascend status | Classification | Last tracking timestamp | ETA | Next action |',
        '|---|---|---|---|---|---|---|'])
    for row in manifest['DELIVERY_WATCH_QUEUE']:
        lines.append('| '+' | '.join(cell(row.get(key)) for key in ('load_number','delivery_appointment','ascend_status',
            'classification','latest_tracking_timestamp','eta','next_action'))+' |')
    lines.extend(['', 'Expected counts: 8 pickups / 3 deliveries. Observed: '+
        str(len(manifest['PICKUP_TRACKING_QUEUE']))+' / '+str(len(manifest['DELIVERY_WATCH_QUEUE']))+'.',
        'Pilot candidate: '+cell(manifest['proposed_pilot'])+'. Authorization-ready: false.',
        'No provider write or communication is authorized by this report. Creation side effects and company wire mapping require review.',
        'Load 1760 delivered is an owner report, not new provider verification. Classifications are FreightDesk-derived.'])
    return '\n'.join(lines)+'\n'


def require_fresh_reconciled_active_manifest(manifest):
    """CarrierView/actions require a newly read, exact Active Loads manifest."""
    if (manifest.get('source_view') != 'Active Loads' or
            manifest.get('reconciliation_status') != 'OPS_BOARD_RECONCILED' or
            not manifest.get('observed_at') or not manifest.get('immutable_evidence_hash')):
        raise PermissionError('fresh_reconciled_active_loads_manifest_required')


def require_current_board_evidence(manifest, current_evidence_hash):
    """A discovery-time hash cannot authorize an action after the board changes."""
    require_fresh_reconciled_active_manifest(manifest)
    if not current_evidence_hash or current_evidence_hash != manifest.get('immutable_evidence_hash'):
        raise PermissionError('active_loads_board_changed_or_not_reread')
