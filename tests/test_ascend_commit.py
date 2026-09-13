import json

import pytest

from app.services.ascend_commit import LIMITATIONS, TENANT, AscendHistoricalCommitter, HistoricalApproval
from app.services.ascend_intelligence import distribution, write_intelligence
from app.services.ascend_staging import AscendRealStager
from app.services.mail_sync import digest
from app.services.store import Store
from tests import test_ascend_staging as fixtures
from tests.test_ascend_staging import source_row, write_source

runtime = fixtures.runtime


def prepare(runtime, rows=None, filename='synthetic.csv'):
    paths, inbox = runtime
    source = write_source(inbox, rows or [source_row()], filename)
    report, _ = AscendRealStager(paths).stage(source, anchors={})
    approval = HistoricalApproval(source_hash=report['source_hash'], batch_id=report['batch_id'],
        mapping_hash=digest(report['mapping']), row_count=report['rows'], currency='USD',
        limitations=LIMITATIONS, authorization='M4A_OWNER_HISTORICAL_COMMIT')
    return AscendHistoricalCommitter(paths), source, approval


def test_commit_reimport_retains_raw_evidence_and_semantics(runtime):
    committer, source, approval = prepare(runtime, [source_row(**{'Last Drop Date':'', 'Load Status':'Completed'})])
    result = committer.commit(source.name, approval)
    assert result['inserted_this_run'] == 1
    before, records = committer.read_committed(approval.batch_id)
    again = committer.commit(source.name, approval)
    assert again['inserted_this_run'] == 0 and again['idempotent_reimport']
    after, repeated = committer.read_committed(approval.batch_id)
    assert before == after and repeated == records
    row = records[0]
    assert row['currency'] == 'USD' and row['data']['currency'] is None
    assert row['data']['historical_carrier_pay'] is None
    assert row['data']['delivery']['date'] is None and row['data']['pickup']['timezone'] is None
    assert row['raw_source']['Exchange Rate Date'] == 'UNVERIFIED FX DATE'
    store = Store(committer.paths.path('Data', TENANT, 'history', 'history.sqlite3'))
    try:
        assert len(store.all(TENANT, 'ascend_commit_receipt')) == 1
        assert not any(store.all(TENANT, kind) for kind in ['shipment', 'task', 'mail_update_proposal'])
        assert sum(a['event'] == 'ASCEND_HISTORY_COMMITTED' for a in store.timeline(TENANT)) == 1
    finally:
        store.close()


@pytest.mark.parametrize('field,value', [('source_hash','wrong'), ('batch_id','wrong'),
    ('mapping_hash','wrong'), ('row_count',2), ('limitations',())])
def test_approval_mismatch_never_commits(runtime, field, value):
    committer, source, approval = prepare(runtime)
    approval = approval.model_copy(update={field:value})
    with pytest.raises(ValueError):
        committer.commit(source.name, approval)


def test_source_change_after_approval_rejected(runtime):
    committer, source, approval = prepare(runtime)
    write_source(source.parent, [source_row(Customer='Changed')], source.name)
    with pytest.raises(ValueError, match='approval_source_mapping_mismatch'):
        committer.commit(source.name, approval)


def test_changed_version_does_not_overwrite_or_partially_insert(runtime):
    committer, source, approval = prepare(runtime)
    committer.commit(source.name, approval)
    before = committer.read_committed(approval.batch_id)
    _, changed, changed_approval = prepare(runtime, [source_row(**{'Load ID':'00043'}),
        source_row(Customer='Changed')], 'changed.csv')
    with pytest.raises(ValueError):
        committer.commit(changed.name, changed_approval)
    assert committer.read_committed(approval.batch_id) == before
    store = Store(committer.paths.path('Data', TENANT, 'history', 'history.sqlite3'))
    try:
        assert len(store.all(TENANT, 'ascend_history_record')) == 1
    finally:
        store.close()


def test_tampered_stage_is_rejected(runtime):
    committer, source, approval = prepare(runtime)
    store = Store(committer.paths.path('Data', TENANT, 'history', 'history.sqlite3'))
    try:
        store.db.execute("UPDATE records SET body=json_set(body,'$.data.raw_customer','Tampered') WHERE kind='ascend_stage_row'")
    finally:
        store.close()
    with pytest.raises(ValueError, match='staged_evidence_mismatch'):
        committer.commit(source.name, approval)


def test_atomic_rollback_on_persistence_failure(runtime, monkeypatch):
    committer, source, approval = prepare(runtime, [source_row(), source_row(**{'Load ID':'00043'})])
    original = Store.put
    def fail(self, tenant, kind, key, value):
        if kind == 'ascend_commit_receipt':
            raise RuntimeError('synthetic failure')
        return original(self, tenant, kind, key, value)
    monkeypatch.setattr(Store, 'put', fail)
    with pytest.raises(RuntimeError):
        committer.commit(source.name, approval)
    store = Store(committer.paths.path('Data', TENANT, 'history', 'history.sqlite3'))
    try:
        assert store.all(TENANT, 'ascend_history_record') == []
    finally:
        store.close()


def test_intelligence_has_exact_provenance_no_private_text_and_raw_groups(runtime):
    rows = [source_row(**{'Load ID':str(i), 'Notes':'QuickPay synthetic secret',
        'First Pick Name':'Synthetic Facility'}) for i in range(3)]
    rows += [source_row(**{'Load ID':'9', 'Customer':'Synthetic Customer ', 'Carrier':'', 'Equipment':''})]
    committer, source, approval = prepare(runtime, rows)
    committer.commit(source.name, approval)
    report, target = write_intelligence(committer, approval.batch_id)
    assert len(report['CustomerProfile']) == 2
    assert report['context']['sample_size'] == 4
    assert len(report['CarrierProfile']) == 1 and len(report['EquipmentUsage']) == 1
    assert {m['field']: m['context']['sample_size'] for m in report['UnassignedIdentityEvidence']} == {
        'raw_carrier': 1, 'raw_equipment': 1}
    assert report['RateHistorySummary']['distributions']['historical_total_expenses']['sum'] == '2800.28'
    for kind in ['CustomerProfile','LaneProfile','CarrierProfile','FacilityProfile','EquipmentUsage']:
        for profile in report[kind]:
            ctx = profile['context']
            assert len(report['evidence_sets'][ctx['evidence_set']]) == ctx['sample_size']
            assert ctx['date_from'] == '2024-09-03' and ctx['calculated_at']
            assert ctx['source_hash'] == approval.source_hash and ctx['raw_vs_derived']
    assert report['candidate_customer_patterns'][0]['matched_context']['sample_size'] == 3
    assert not report['candidate_customer_patterns'][0]['approved']
    text = (target/'historical-intelligence.md').read_text(encoding='utf-8')
    assert 'synthetic secret' not in json.dumps(report) and '832-555-0199' not in text
    assert 'carrier pay' in text and 'NOT current market rates' in text


def test_decimal_distributions():
    result = distribution(['-10', '0', '10', '100'])
    assert result['median'] == '5.0' and result['p25'] == '-2.50'
    assert result['negative'] == 1 and result['zero'] == 1
    assert distribution([])['mean'] is None


def test_commit_command_backup_and_verification(runtime):
    from scripts.commit_ascend_history import execute
    committer, source, approval = prepare(runtime)
    folder = committer.paths.path('Data', TENANT, 'history', 'approvals')
    folder.mkdir(parents=True)
    (folder/'synthetic.json').write_text(approval.model_dump_json(), encoding='utf-8')
    result = execute(source.name, 'synthetic.json')
    assert result['total_committed_records'] == 1
    assert result['reimport_records_and_audit_unchanged'] and result['sqlite_integrity'] == 'ok'
    assert result['post_commit_validation']['source_to_staged_financial_mismatches'] == []
    assert committer.paths.path('Data', TENANT, 'history', 'backups',
        approval.batch_id+'-before-commit.sqlite3').exists()
