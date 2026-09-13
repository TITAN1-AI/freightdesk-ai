"""Evidence-led POC002 decisions. Owner oracle is used only after independent classification."""
import re
from datetime import timedelta

from app.models.domain import utcnow
from app.services.live_ops import TrackingEvidence, delivery_classification, tracking_inputs, value
from app.services.live_ops_carrierview import DELIVERIES, PICKUPS


def assignment(candidate):
    carrier=value(candidate,'carrier')
    assigned=value(candidate,'carrier_assigned')
    driver=value(candidate,'driver')
    # Unknown/null is not an observed empty assignment; placeholder text is not proof either.
    if assigned and assigned.strip().lower() in {'no','false','unassigned'}:
        return 'NEEDS_REVIEW' if carrier and carrier.strip() else 'UNCOVERED'
    if carrier is not None and not carrier.strip() and driver is not None and not driver.strip():
        return 'UNCOVERED'
    def present(v):
        return bool(v and v.strip().lower() not in {'','n/a','na','none','unknown','unassigned','tbd','-','?'})
    mc=value(candidate,'carrier_mc') or ''
    positive=(assigned and assigned.strip().lower() in {'yes','true','assigned'}) or bool(
        re.fullmatch(r'(?:MC[\s#:-]*)?\d{3,10}',mc.strip(),re.I))
    if present(carrier) and positive:
        return 'COVERED' if all(present(value(candidate,k)) for k in ('driver','truck','trailer')) else 'ASSIGNMENT_INCOMPLETE'
    return 'UNKNOWN'


def missing_contact_fields(candidate):
    return [k for k in ('driver','driver_phone','truck','trailer','dispatcher_email') if not value(candidate,k)]


def outlook_targets(candidates):
    return [c for c in candidates if c.pickup_due and assignment(c) in {'COVERED','ASSIGNMENT_INCOMPLETE'}
            and missing_contact_fields(c)]


def email_proposals(candidate,messages,now=None):
    """Strong association first; extracted claims never become verified operational facts."""
    now=now or utcnow()
    address=value(candidate,'dispatcher_email')
    if not address:
        return []
    result=[]
    for m in messages:
        if (m.isDraft or not m.from_ or m.from_.emailAddress.address.casefold()!=address.casefold() or
                not m.receivedDateTime or not timedelta(0)<=now-m.receivedDateTime<=timedelta(days=14)):
            continue
        text=m.subject+'\n'+m.body.content
        refs=set(re.findall(r'\b(?:booking(?:\s+load)?|load)\s*(?:id|number|no\.?|#|:)??\s*[:#-]?\s*(\d{4,20})\b',text,re.I))
        if refs!={candidate.load_number}:
            continue
        claims={}
        for label,key in [('Driver','driver'),('Driver Phone','driver_phone'),('Truck','truck'),('Trailer','trailer')]:
            matches=re.findall(r'^'+label+r'\s*:\s*([^\r\n]{1,100})$',text,re.I|re.M)
            if len(set(matches))==1:
                claims[key]=matches[0].strip()
        if claims:
            result.append({'load_id':candidate.load_number,'message_id':m.id,'conversation_id':m.conversationId,
                'received_at':m.receivedDateTime.isoformat(),'fields':claims,'source':'Outlook',
                'association':'exact_labeled_load_reference_and_verified_dispatcher_email',
                'verified':False,'state':'REVIEW_REQUIRED'})
    return result


def report(candidates,tracking,mail_proposals=(),now=None):
    now=now or utcnow()
    if len(candidates)!=11 or {c.load_number for c in candidates}!=PICKUPS|DELIVERIES:
        raise ValueError('exact_operational_scope_required')
    rows=[]
    pilot=[]
    for c in sorted(candidates,key=lambda x:int(x.load_number)):
        t=tracking.get(c.load_number,TrackingEvidence(load_number=c.load_number))
        if t.load_number!=c.load_number:
            raise ValueError('provider_identity_mismatch')
        payload,missing=tracking_inputs(c)
        coverage=assignment(c)
        fresh=bool(c.facts) and all(timedelta(0)<=now-f.observed_at<=timedelta(hours=4) for f in c.facts.values() if f.verified)
        cv_fresh=t.observed_at and timedelta(0)<=now-t.observed_at<=timedelta(minutes=15)
        if not fresh:
            coverage='UNKNOWN'
        if c.pickup_due:
            state='UNKNOWN'
            if coverage=='UNCOVERED':
                state='UNCOVERED'
            elif coverage=='ASSIGNMENT_INCOMPLETE':
                state='MISSING_ASSIGNMENT_DATA'
            elif coverage=='NEEDS_REVIEW' or t.existence=='DUPLICATE':
                state='NEEDS_REVIEW'
            elif coverage=='COVERED':
                if t.existence=='EXISTS':
                    state='ALREADY_TRACKING' if cv_fresh and t.semantics_verified and t.tracking_active else 'NEEDS_REVIEW'
                elif any('phone' in k for k in missing):
                    state='MISSING_DRIVER_CONTACT'
                elif missing:
                    state='MISSING_STOP_DATA'
                elif cv_fresh and t.existence in {'NOT_FOUND_IN_BOUNDED_READ','ABSENT_VERIFIED'}:
                    state='READY_FOR_TRACKING'  # Review/pilot eligibility only, never a creation grant.
            if state=='READY_FOR_TRACKING' and payload and len(c.stops)==2:
                pilot.append(c)
            action={'UNCOVERED':'COVERAGE_REQUIRED','MISSING_ASSIGNMENT_DATA':'VERIFY_ASSIGNMENT',
                'MISSING_DRIVER_CONTACT':'TARGETED_OUTLOOK_READ_OR_OWNER_REVIEW','MISSING_STOP_DATA':'VERIFY_ASCEND_STOPS',
                'ALREADY_TRACKING':'NO_CREATION','READY_FOR_TRACKING':'OWNER_PILOT_REVIEW'}.get(state,'REVIEW_EVIDENCE')
        else:
            state,_=delivery_classification(c,t,now)
            if state not in {'TRACKING_ACTIVE','TRACKING_STALE','EN_ROUTE_DELIVERY','CHECKED_IN_DELIVERY','DELIVERED'}:
                state='UNKNOWN'
            action='DELIVERY_WATCH_NO_CREATION' if t.existence=='EXISTS' else 'REVIEW_TRACKING_EVIDENCE'
        proposals=[p for p in mail_proposals if p['load_id']==c.load_number]
        rows.append({'load_id':c.load_number,'queue':'pickup' if c.pickup_due else 'delivery',
            'fact_presence':{k:bool(value(c,k)) for k in ('load_number','status','pickup_date','delivery_date',
                'carrier','driver','driver_phone','truck','trailer','truck_status','reference')},
            'operational_state':state,'carrier_coverage':coverage,'required_fields_complete':not missing,
            'missing_required_facts':missing,'carrierview_result':'NOT_FOUND_IN_BOUNDED_SEARCH' if
                t.existence=='NOT_FOUND_IN_BOUNDED_READ' else t.existence,'provider_ids':t.provider_ids,
            'list_filters':t.observed_list_filters,'integration_kind':t.integration_kind,
            'provider_flags':t.provider_flags,'last_position_available':t.last_position_available,
            'position_age_seconds':max(0,(now-t.last_position_at).total_seconds()) if t.last_position_at and t.last_position_at<=now else None,
            'next_action':action,'action_authorized':False,'action_state':'QUEUED_FOR_REVIEW',
            'missing_fact_sources':{k:('Outlook exact-load claims then review' if 'phone' in k else
                'Ascend exact-load details then owner review') for k in missing},
            'sources':sorted({f.source_reference for f in c.facts.values() if f.verified}),
            'carrierview_source':t.source_reference,'email_claims_pending_review':len(proposals),
            'pod_state':'UNVERIFIED','fresh_ascend_evidence':fresh})
    # Owner validation oracle is isolated here, after all load decisions. Never used by assignment().
    pickups=[r for r in rows if r['queue']=='pickup']
    observed={'pickups':len(pickups),'covered':sum(r['carrier_coverage']=='COVERED' for r in pickups),
        'uncovered':sum(r['carrier_coverage']=='UNCOVERED' for r in pickups),
        'delivery_records':sum(r['queue']=='delivery' and r['carrierview_result']=='EXISTS' for r in rows)}
    expected={'pickups':8,'covered':7,'uncovered':1,'delivery_records':3}
    selected=min(pilot,key=lambda c:int(c.load_number)) if pilot else None
    return {'status':'POC_002_MULTI_SYSTEM_RECONCILED' if observed==expected else 'POC_002_RECONCILIATION_MISMATCH',
        'calculated_at':now.isoformat(),'observed':observed,'owner_validation_oracle':expected,'loads':rows,
        'discrepancy_load_ids':[r['load_id'] for r in rows if
            (r['queue']=='pickup' and r['carrier_coverage'] not in {'COVERED','UNCOVERED'}) or
            (r['queue']=='delivery' and r['carrierview_result']!='EXISTS')],
        'count_mismatch_attribution':'Compare all per-load states; oracle does not identify which load should change.',
        'pilot_load_id':selected.load_number if selected else None,
        'pilot_summary':{'stop_count':2,'phone_verified':True,'payload_values':'PRIVATE_RUNTIME_ONLY',
            'required_fact_provenance':{k:f.source_reference for k,f in selected.facts.items() if f.verified},
            'stop_provenance':[s.get('source_reference') for s in selected.stops]} if selected else None,
        'pilot_missing_facts':[] if selected else ['No unambiguous eligible load with complete verified fields and fresh bounded reconciliation'],
        'approval_required':'One exact native POST /api/loads after owner reviews payload, bounded-search duplicate risk, company wire mapping and communication side effects.',
        'creation_execution_enabled':False,'canonical_mutation':False,'live_validated':False}
