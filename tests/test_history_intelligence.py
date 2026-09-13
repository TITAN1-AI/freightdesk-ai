from decimal import Decimal
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from app.core.runtime import RuntimePaths
from app.models.domain import Role
from app.models.history import SchemaMapping
from app.services.history import AscendHistoricalImporter, HistoricalIntelligence
from app.services.store import Store


@pytest.fixture
def history(tmp_path):
    store = Store(tmp_path / 'history.sqlite3')
    yield store, AscendHistoricalImporter(store), HistoricalIntelligence(store)
    store.close()


def export(rows):
    return {'headers':['Ref','Client','Revenue','Cost','Pickup','Notes','Currency'], 'rows':rows,
            'source_hash':str(rows)}


def mapping(**changes):
    return SchemaMapping(columns={'load_number':'Ref','customer':'Client','customer_revenue':'Revenue',
        'carrier_pay':'Cost','pickup_date':'Pickup','notes':'Notes','currency':'Currency'},
        reviewed_by='fixture-owner', reviewed=True, **changes)


def row(ref='1', revenue='1500.10', cost='1000.05', currency='USD'):
    return {'Ref':ref,'Client':'Synthetic Customer','Revenue':revenue,'Cost':cost,
            'Pickup':'2025-09-03','Notes':'Appointment required','Currency':currency}


def test_history_requires_actual_schema_review(history):
    _, importer, _ = history
    with pytest.raises(PermissionError):
        importer.stage(export([row()]), mapping().model_copy(update={'reviewed':False}), 'fixture.csv')
    bad = mapping().model_copy(update={'columns':{'load_number':'AssumedField'}})
    with pytest.raises(ValueError):
        importer.stage(export([row()]), bad, 'fixture.csv')


@pytest.mark.parametrize('change', [{'Revenue':'NaN'}, {'Currency':''}, {'Pickup':'9/3/25'},
    {'Revenue':'=SUM(A1:A2)'}, {'Ref':''}])
def test_history_invalid_values_quarantine(history, change):
    store, importer, _ = history
    result = importer.stage(export([{**row(), **change}]), mapping(), 'fixture.csv')
    assert result['invalid'] == 1 and result['valid'] == 0
    assert not store.all('booking-logistics','history_record')


def test_history_duplicates_conflicts_and_canonical_isolation(history, owner):
    store, importer, _ = history
    first = importer.stage(export([row()]), mapping(), 'first.csv')
    assert importer.commit(first['batch_id'], owner)['inserted'] == 1
    assert importer.commit(first['batch_id'], owner)['duplicates'] == 1
    changed = importer.stage(export([row(revenue='1700')]), mapping(), 'changed.csv')
    result = importer.commit(changed['batch_id'], owner)
    assert result == {'inserted':0,'duplicates':0,'conflicts':1,'live_shipments_changed':0}
    assert len(store.all(owner.tenant_id,'history_record')) == 1
    assert not store.all(owner.tenant_id,'shipment')
    record = store.all(owner.tenant_id,'history_record')[0]
    assert record['provenance']['source_identifier'] == 'first.csv'
    assert record['provenance']['source_version'] and record['provenance']['imported_at']


def test_history_decimal_statistics_currency_samples_and_rules(history, owner):
    _, importer, intelligence = history
    rows = [row('1'), row('2','1800.20','1300.15'), row('3','2200.30','1800.20'), row('4','99','9','CAD')]
    batch = importer.stage(export(rows), mapping(), 'synthetic.csv')
    importer.commit(batch['batch_id'], owner)
    for kind in ('CustomerProfile','LaneProfile','CarrierProfile','FacilityProfile'):
        profile = intelligence.profile(kind, customer='Synthetic Customer')
        assert profile.sample_size == 4 and len(profile.source_records) == 4
        assert str(profile.date_from) == '2025-09-03' and profile.calculated_at
        usd = next(r for r in profile.rates if r.metric == 'customer_revenue' and r.currency == 'USD')
        assert usd.sample_size == 3 and usd.median == Decimal('1800.20')
        assert usd.average == Decimal('5500.60') / 3 and usd.historical_only
    rule = intelligence.propose_customer_rule('Synthetic Customer','Appointment required')
    assert rule.status == 'PROPOSED'
    with pytest.raises(PermissionError):
        intelligence.approve_customer_rule(rule.id, owner.model_copy(update={'role':Role.OPERATIONS_USER}))
    assert intelligence.approve_customer_rule(rule.id, owner).status == 'APPROVED'


def test_history_missing_data_is_not_filled_and_one_note_not_sop(history, owner):
    _, importer, intelligence = history
    batch = importer.stage(export([row(revenue='',cost='')]), mapping(), 'empty-rates.csv')
    importer.commit(batch['batch_id'], owner)
    profile = intelligence.profile('CustomerProfile', customer='Synthetic Customer')
    assert all(r.sample_size == 0 and r.average is None for r in profile.rates)
    with pytest.raises(ValueError):
        intelligence.propose_customer_rule('Synthetic Customer','Appointment required')


def test_csv_and_xlsx_inspection_use_runtime_and_reject_formulas(tmp_path, monkeypatch):
    # All test artifacts already live under the approved nonsynced TestRuns root.
    paths = SimpleNamespace(path=lambda *parts: tmp_path.joinpath(*parts))
    monkeypatch.setattr(RuntimePaths, 'from_environment', lambda: paths)
    inbox = paths.path('Data','booking-logistics','history','inbox')
    inbox.mkdir(parents=True)
    csv = inbox / 'fixture.csv'
    csv.write_text('Actual Ref,Actual Client\n1,Synthetic Customer\n', encoding='utf-8')
    result = AscendHistoricalImporter.read_export(csv)
    assert result['headers'] == ['Actual Ref','Actual Client'] and len(result['source_hash']) == 64
    with pytest.raises(PermissionError):
        AscendHistoricalImporter.read_export(tmp_path / 'outside.csv')
    book = Workbook()
    book.active.append(['Actual Ref','Actual Client'])
    book.active.append(['1','Synthetic Customer'])
    xlsx = inbox / 'fixture.xlsx'
    book.save(xlsx)
    assert AscendHistoricalImporter.read_export(xlsx)['rows'][0]['Actual Ref'] == '1'
    book.active['B2'] = '=WEBSERVICE("https://example.test")'
    book.save(xlsx)
    book.close()
    with pytest.raises(PermissionError):
        AscendHistoricalImporter.read_export(xlsx)
