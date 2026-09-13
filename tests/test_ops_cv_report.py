from datetime import date

import pytest

from app.models.domain import utcnow
from app.services.live_ops import OpsCandidate, TrackingEvidence
from app.services.live_ops_carrierview import (
    DELIVERIES, MANIFEST_ID, PICKUPS, reconciliation_report, validate_reconciliation_scope,
)


def fixture():
    candidates=[OpsCandidate(load_number=n,service_date=date(2026,9,11),identity_verified=True,
        pickup_due=n in PICKUPS,delivery_due=n in DELIVERIES) for n in sorted(PICKUPS|DELIVERIES)]
    manifest={'id':MANIFEST_ID,'service_date':'2026-09-11','source_view':'Active Loads',
        'reconciliation_status':'OPS_BOARD_RECONCILED','observed_at':utcnow().isoformat(),
        'immutable_evidence_hash':'synthetic-hash',
        'PICKUP_TRACKING_QUEUE':[{'load_number':n} for n in PICKUPS],
        'DELIVERY_WATCH_QUEUE':[{'load_number':n} for n in DELIVERIES]}
    tracking={n:TrackingEvidence(load_number=n,existence='NOT_FOUND_IN_BOUNDED_READ') for n in PICKUPS|DELIVERIES}
    return manifest,candidates,tracking


def test_report_conservative_and_exact_scope():
    m,c,t=fixture()
    t['1755']=TrackingEvidence(load_number='1755',existence='EXISTS',provider_ids=['123'],
        observed_list_filters=['active'],provider_flags={'delivery_arrived':False})
    r=reconciliation_report(m,c,t)
    assert len(r['pickups'])==8 and len(r['deliveries'])==3
    assert r['proposed_pilot'] is None and not r['production_writes']
    assert r['pickups'][0]['classification']=='NEEDS_REVIEW'
    assert r['pickups'][0]['creation_blocked_by_existing_record']
    assert all(p['classification']!='READY_FOR_TRACKING_REVIEW' for p in r['pickups'])
    assert all(d['classification']=='UNKNOWN' and d['pod_status']=='UNKNOWN' for d in r['deliveries'])
    assert r['pickups'][1]['carrierview_result']=='NOT_FOUND_IN_BOUNDED_SEARCH'
    assert 'driver_phone_not_observed_or_unverified' in r['pickups'][0]['missing_required_facts']


def test_wrong_manifest_or_candidate_stops_before_reads():
    m,c,_=fixture()
    with pytest.raises(PermissionError):
        validate_reconciliation_scope(m|{'id':'other'},c)
    with pytest.raises(PermissionError):
        validate_reconciliation_scope(m,c[:-1])
