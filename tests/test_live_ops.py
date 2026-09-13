import asyncio
import json
import os
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.models.domain import utcnow
from app.services.live_ops import (
    OpsActionLedger, OpsCandidate, OpsFact, TrackingEvidence, build_manifest, delivery_classification,
    pickup_classification, tracking_inputs, require_current_board_evidence, require_fresh_reconciled_active_manifest,
)
from integrations.ascend.ops_board import all_loads_cross_check
from app.services.live_ops_carrierview import reconcile_ops
from app.services.store import Store
from integrations.ascend.field_discovery import ReadOnly1752Executor
from integrations.ascend.ops_discovery import local_date, select_board


def candidate(number='90001'):
    now = utcnow()
    return OpsCandidate(load_number=number, service_date=date(2026,9,11), pickup_due=True,
        delivery_due=True, identity_verified=True, additional_stops_verified=True,
        facts={'driver_phone':OpsFact(value='+15555550123', source='AscendTMS', verified=True,
                                    source_reference='synthetic:phone', observed_at=now)},
        stops=[{'type':t, 'company':'Synthetic facility', 'address':'Synthetic address',
            'dateFrom':'2026-09-11T10:00:00-05:00', 'dateTo':'2026-09-11T12:00:00-05:00',
            'verified':True} for t in ('pickup','destination')])


def absence(number='90001'):
    return TrackingEvidence(load_number=number, existence='ABSENT_VERIFIED', observed_at=utcnow())


def test_local_dates_require_year_and_no_timezone_conversion():
    assert local_date('2026-09-11T23:00:00-07:00') == date(2026,9,11)
    assert local_date('09/11/2026 10:00 AM', 'US') == date(2026,9,11)
    assert local_date('09/11/2026 10:00 AM') is None
    assert local_date('09/11') is None
    assert local_date('tomorrow') is None
    assert local_date('2026-02-31') is None


def test_board_discovery_does_not_force_expected_counts_or_read_historical_target():
    rows = [{'load_number':'90001','pickup_date':'09/11/2026','delivery_date':'09/12/2026'},
            {'load_number':'90002','pickup_date':'09/10/2026','delivery_date':'09/11/2026'},
            {'load_number':'1752','pickup_date':'09/03/2026','delivery_date':'09/04/2026'},
            {'load_number':'90003','pickup_date':'unknown','delivery_date':'unknown'}]
    selected, unknown = select_board(rows,date(2026,9,11),'US')
    assert set(selected) == {'90001','90002'} and unknown == 1
    with pytest.raises(Exception, match='conflict'):
        select_board(rows+[rows[0] | {'delivery_date':'09/13/2026'}], date(2026,9,11),'US')


def board_candidate(number, *, pickup=False, delivery=False):
    return OpsCandidate(load_number=str(number), service_date=date(2026,9,11), pickup_due=pickup,
        delivery_due=delivery, identity_verified=True)


def test_active_loads_exact_manifest_counts_and_same_day_event_is_in_both_queues_once():
    candidates = ([board_candidate(10000+i, pickup=True) for i in range(7)] +
                  [board_candidate(10007, pickup=True, delivery=True)] +
                  [board_candidate(10100+i, delivery=True) for i in range(2)])
    manifest = build_manifest('active-exact-001', date(2026,9,11), candidates, {}, coverage='COMPLETE_CURRENT_BOARD',
        source_view='Active Loads', board_row_count=10, evidence_hash='evidence-a')
    assert manifest['reconciliation_status'] == 'OPS_BOARD_RECONCILED'
    assert len(manifest['PICKUP_TRACKING_QUEUE']) == 8 and len(manifest['DELIVERY_WATCH_QUEUE']) == 3
    assert [x['load_number'] for x in manifest['PICKUP_TRACKING_QUEUE']].count('10007') == 1
    assert [x['load_number'] for x in manifest['DELIVERY_WATCH_QUEUE']].count('10007') == 1
    assert manifest['source_view'] == 'Active Loads' and manifest['immutable_evidence_hash'] == 'evidence-a'


def test_duplicate_rows_mismatch_and_stale_board_fail_closed():
    duplicated = [board_candidate(10001, pickup=True), board_candidate(10001, pickup=True)]
    with pytest.raises(ValueError, match='identity'):
        build_manifest('active-dupe-001', date(2026,9,11), duplicated, {}, source_view='Active Loads', evidence_hash='x')
    mismatch = build_manifest('active-mismatch-001', date(2026,9,11), [board_candidate(10001, pickup=True)], {},
        source_view='Active Loads', evidence_hash='old')
    assert mismatch['reconciliation_status'] == 'OPS_BOARD_MISMATCH'
    with pytest.raises(PermissionError, match='fresh_reconciled'):
        require_fresh_reconciled_active_manifest(mismatch)
    reconciled = mismatch | {'reconciliation_status':'OPS_BOARD_RECONCILED'}
    with pytest.raises(PermissionError, match='changed_or_not_reread'):
        require_current_board_evidence(reconciled, 'new')


def test_all_loads_is_audit_only_and_extra_service_date_records_never_expand_active_queue():
    active = [board_candidate(10001, pickup=True), board_candidate(10002, delivery=True)]
    all_rows = active + [board_candidate(19999, pickup=True, delivery=True)]
    check = all_loads_cross_check(active, all_rows)
    assert check == {'active_loads_missing_from_all_loads': [], 'NON_ACTIVE_SERVICE_DATE_RECORDS': ['19999']}
    manifest = build_manifest('active-audit-001', date(2026,9,11), active, {}, source_view='Active Loads',
        evidence_hash='audit', cross_check=check)
    assert manifest['NON_ACTIVE_SERVICE_DATE_RECORDS'] == ['19999']
    assert '19999' not in {row['load_number'] for row in manifest['PICKUP_TRACKING_QUEUE']}


def test_pickup_ready_requires_fresh_verified_absence_and_complete_known_stops():
    c = candidate()
    assert pickup_classification(c,absence())[0] == 'READY_FOR_TRACKING'
    assert pickup_classification(c,TrackingEvidence(load_number=c.load_number,existence='NOT_FOUND_IN_BOUNDED_READ'))[0] == 'NEEDS_REVIEW'
    assert pickup_classification(c,absence().model_copy(update={'observed_at':utcnow()-timedelta(hours=1)}))[0] == 'NEEDS_REVIEW'
    c.additional_stops_verified = False
    assert pickup_classification(c,absence())[0] == 'MISSING_REQUIRED_STOP_DATA'
    c = candidate()
    c.stops[0]['dateFrom'] = '2026-09-11T10:00:00'
    assert tracking_inputs(c)[0] is None


def test_unobserved_phone_is_unknown_not_provider_missing_and_existing_load_never_recreated():
    c = candidate()
    c.facts = {}
    assert pickup_classification(c,absence())[0] == 'NEEDS_REVIEW'
    c = candidate()
    c.facts['driver_phone'].value = ''
    assert pickup_classification(c,absence())[0] == 'MISSING_DRIVER_PHONE'
    c = candidate()
    exists = TrackingEvidence(load_number=c.load_number, existence='EXISTS', provider_ids=['123'])
    assert pickup_classification(c,exists)[2] is None
    exists.tracking_active, exists.semantics_verified = True, True
    assert pickup_classification(c,exists)[0] == 'ALREADY_TRACKING'
    assert pickup_classification(candidate('1760'),absence('1760'))[0] == 'NEEDS_REVIEW'


def test_delivery_missing_old_or_unverified_evidence_never_fabricates_real_time():
    c = candidate()
    t = TrackingEvidence(load_number=c.load_number,existence='EXISTS',observed_at=utcnow(),
                         tracking_active=True,last_position_at=utcnow())
    assert delivery_classification(c,t)[0] == 'UNKNOWN'
    t.semantics_verified = True
    assert delivery_classification(c,t)[0] == 'TRACKING_ACTIVE'
    t.last_position_at = utcnow()-timedelta(hours=2)
    assert delivery_classification(c,t)[0] == 'TRACKING_STALE'
    t.delivered = True
    assert delivery_classification(c,t)[0] == 'DELIVERED'
    t.observed_at = utcnow()-timedelta(hours=2)
    assert delivery_classification(c,t)[0] == 'UNKNOWN'


def test_durable_proposal_hash_idempotency_no_dispatch_or_canonical_mutation(tmp_path):
    store = Store(tmp_path/'ops.sqlite3')
    try:
        ledger = OpsActionLedger(store)
        c = candidate()
        manifest = build_manifest('synthetic-ops',c.service_date,[c],{c.load_number:absence()},ledger=ledger)
        assert manifest['pickup_count_difference'] == -7 and manifest['delivery_count_difference'] == -2
        assert manifest['proposed_pilot'] == c.load_number and not manifest['pilot_authorization_ready']
        assert '+15555550123' not in json.dumps(manifest)
        action = store.all('booking-logistics','ops_proposed_action')[0]
        assert action['attempts'] == 0 and action['state'] == 'AWAITING_OWNER_REVIEW'
        assert action['payload']['driver_phone'] == '+15555550123'
        assert not action['payload'].get('emails') and not action['payload'].get('dispatchers')
        assert action['unresolved_contract_fields']
        build_manifest('synthetic-ops',c.service_date,[c],{c.load_number:absence()},ledger=ledger)
        assert len(store.all('booking-logistics','ops_proposed_action')) == 1
        assert not store.all('booking-logistics','shipment') and not hasattr(ledger,'dispatch')
        c.facts['driver_phone'].value = '+15555550124'
        with pytest.raises(ValueError,match='changed_payload'):
            build_manifest('synthetic-ops',c.service_date,[c],{c.load_number:absence()},ledger=ledger)
    finally:
        store.close()


def test_multistop_preserved_and_two_stop_pilot_preferred(tmp_path):
    store = Store(tmp_path/'ops.sqlite3')
    try:
        c = candidate()
        c.stops.insert(1,dict(c.stops[0]))
        manifest = build_manifest('synthetic-multistop',c.service_date,[c],{c.load_number:absence()},ledger=OpsActionLedger(store))
        assert len(store.all('booking-logistics','ops_proposed_action')[0]['payload']['locations']) == 3
        assert manifest['proposed_pilot'] is None
    finally:
        store.close()


def test_generalized_executor_still_requires_discovered_authorized_identity():
    with pytest.raises(Exception,match='outside_discovered_scope'):
        ReadOnly1752Executor(None,lambda:True,load_number='90001')
    executor = ReadOnly1752Executor(None,lambda:True,load_number='90001',authorized_loads=('90001',))
    assert executor.load_number == '90001'


def test_carrierview_reconciliation_bounded_gets_exact_targets_and_no_absence_assumption():
    calls = []
    class Adapter:
        config = SimpleNamespace(credential_class=SimpleNamespace(value='tenant'),discovery_provider_id=None)
        def provider_id(self, value):
            return str(value)
        async def _request(self, method, path, operation, **kwargs):
            assert method == 'GET' and 'body' not in kwargs
            calls.append(path)
            if path == '/api/profile':
                return {'company_name':'Booking Logistics LLC'},0
            if path == '/api/loads':
                return {'data':[{'load_id':'90001','id':'123'}, {'load_id':'UNRELATED','id':'456'}]},0
            assert path == '/api/loads/123'
            return {'data':{'load_id':'90001','id':'123','driver_phone':'SECRET_PHONE',
                'last_position':{'timestamp':'2026-09-11T11:00:00Z'},'route_started':True}},0
    result = asyncio.run(reconcile_ops(Adapter(),['90001','90002']))
    assert len(calls) == 4 and '/api/loads/456' not in calls
    assert result['90001'].existence == 'EXISTS' and not result['90001'].semantics_verified
    assert result['90002'].existence == 'NOT_FOUND_IN_BOUNDED_READ'
    assert 'SECRET_PHONE' not in json.dumps({k:v.model_dump(mode='json') for k,v in result.items()})


def test_real_browser_exact_operational_detail_offline(tmp_path):
    from integrations.ascend.ops_discovery import read_candidate
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as runtime:
            context = await runtime.chromium.launch_persistent_context(str(tmp_path/'profile'),channel='msedge',
                headless=True, env={**os.environ,'TEMP':str(tmp_path),'TMP':str(tmp_path)})
            try:
                nav = '<nav>'+''.join('<a href="#">'+n+'</a>' for n in ['Dashboard','Loads','Customers','Carriers'])+'</nav>'
                board = nav+'<table><thead><tr><th>Load Number</th><th>Pickup Date</th><th>Delivery Date</th></tr></thead>'
                board += '<tbody><tr><td><a href="/detail/90001">90001</a></td><td>09/11/2026</td><td>09/12/2026</td></tr></tbody></table>'
                values = {'Load Number':'90001','Pickup Date':'09/11/2026','Delivery Date':'09/12/2026',
                    'Driver Phone':'+15555550123','Stop Count':'2', 'Pickup Address':'Synthetic pickup',
                    'Pickup Company':'Synthetic company', 'Pickup Start':'2026-09-11T10:00:00-05:00',
                    'Pickup End':'2026-09-11T12:00:00-05:00','Delivery Address':'Synthetic delivery',
                    'Delivery Company':'Synthetic company','Delivery Start':'2026-09-12T10:00:00-05:00',
                    'Delivery End':'2026-09-12T12:00:00-05:00'}
                detail = nav+''.join('<label for="f'+str(i)+'">'+key+'</label><input id="f'+str(i)+'" value="'+value+'">'
                                     for i,(key,value) in enumerate(values.items()))
                detail += '<label for="note">Private Notes</label><textarea id="note">SECRET_NOTE</textarea>'
                async def fulfill(route):
                    await route.fulfill(content_type='text/html',body=detail if '/detail/' in route.request.url else board)
                await context.route('**/*',fulfill)
                page = await context.new_page()
                await page.goto('https://ascendtms.com/loads')
                # Detail executor regression remains separate from the observed 33-column board contract.
                selected,_ = select_board([{'load_number':'90001','pickup_date':'09/11/2026',
                    'delivery_date':'09/12/2026'}],date(2026,9,11),'US')
                assert set(selected) == {'90001'}
                c = await read_candidate(page,'90001',tuple(selected),selected['90001'],date(2026,9,11),lambda:True,'synthetic-ops','US')
                assert c.pickup_due and not c.delivery_due and c.notes_present
                assert c.additional_stops_verified and len(c.stops) == 2
                assert tracking_inputs(c)[0] is not None
                assert 'SECRET_NOTE' not in c.model_dump_json() and '+15555550123' not in repr(c)
            finally:
                await context.close()
    asyncio.run(run())
