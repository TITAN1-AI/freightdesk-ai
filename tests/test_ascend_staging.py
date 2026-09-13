import csv
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.runtime import RuntimePaths
from app.models.ascend_history import AscendHistoricalEvidence
from app.services.ascend_staging import (
    HEADERS, AscendRealStager, decimal_value, identities_and_equipment, normalize,
    schema_mapping, scoped_note_patterns, summarize,
)
from app.services.store import Store


def source_row(**changes):
    row = dict.fromkeys(HEADERS,'')
    row.update({'Load ID':'00042','Customer':'Synthetic Customer','Carrier':'Synthetic Carrier',
        'Carrier MC Number':'001234','Carrier USDOT Number':'0009876','First Pick City':'Alpha',
        'First Pick State':'TX','Last Drop City':'Beta','Last Drop State':'OK','First Pick Postal':'00123',
        'First Pick Date':'09/03/2024 07:00','Last Drop Date':'09/04/2024',
        'Load Created Date':'2024-08-28T20:57:54.596Z','Total Income':'$1000.10',
        'Total Expenses':'$700.07','Gross Profit/Loss':'$300.03','Gross Profit/Loss %':'30.00',
        'Equipment':"48' Flatbed/Step Deck",'Exchange Rate Date':'UNVERIFIED FX DATE',
        'Notes':'SYNTHETIC PRIVATE NOTE','Private Notes':'SYNTHETIC PRIVATE NOTES',
        'Drivers':'Synthetic Person 832-555-0199','Weight':'44000','Pickups':'Raw intermediate source evidence'})
    row.update(changes)
    return row


def fixture_export(rows):
    from app.services.mail_sync import digest
    return {'headers':HEADERS,'rows':rows,'source_hash':digest(rows)}


@pytest.fixture
def runtime(tmp_path,monkeypatch):
    paths = SimpleNamespace(path=lambda *parts:tmp_path.joinpath(*parts))
    monkeypatch.setattr(RuntimePaths,'from_environment',lambda:paths)
    inbox=paths.path('Data','booking-logistics','history','inbox')
    inbox.mkdir(parents=True)
    return paths,inbox


def write_source(inbox, rows, filename='synthetic.csv'):
    path=inbox/filename
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_typed_evidence_retains_financial_and_date_semantics():
    staged=normalize(source_row(),2)
    assert not staged['errors'] and not staged['warnings']
    typed=AscendHistoricalEvidence.model_validate(staged['data'])
    assert typed.carrier_mc=='001234' and typed.carrier_dot=='0009876'
    assert typed.pickup.postal=='00123' and typed.pickup.local_datetime.tzinfo is None
    assert typed.pickup.timezone is None and typed.delivery.local_datetime is None
    assert typed.created_at.utcoffset().total_seconds()==0
    assert typed.historical_total_expenses==Decimal('700.07') and typed.historical_carrier_pay is None
    assert typed.currency is None and typed.weight_unit is None
    assert 'Exchange Rate Date' not in staged['data']
    assert staged['raw_source']['Exchange Rate Date']=='UNVERIFIED FX DATE'
    assert staged['raw_source']['Pickups']=='Raw intermediate source evidence'


@pytest.mark.parametrize('value',['NaN','Infinity','1,23','1e3','=$100','', '0.001'])
def test_money_parser_fails_closed(value):
    with pytest.raises(ValueError):
        decimal_value(value,money=True)


def test_decimal_money_and_negative_values():
    assert decimal_value('$1,234.56',money=True)==Decimal('1234.56')
    assert decimal_value('$-20.01',money=True)==Decimal('-20.01')


@pytest.mark.parametrize('field,value,error',[
    ('First Pick Date','02/30/2024','invalid_date'),
    ('Load Created Date','2024-09-03T07:00:00','invalid_date'),
    ('Total Expenses','$699.07','arithmetic_mismatch'),
    ('Gross Profit/Loss %','31.00','rounded_margin_mismatch'),
    ('Total Income','NaN','invalid_money'),
    ('Weight','unknown','invalid_number'),
    ('Load ID','','invalid_identifier'),
])
def test_invalid_rows_remain_quarantined(field,value,error):
    staged=normalize(source_row(**{field:value}),2)
    assert staged['status']=='INVALID' and any(error in entry for entry in staged['errors'])


def test_mc_dot_warning_preserves_source_string():
    staged=normalize(source_row(**{'Carrier MC Number':'MC-00123'}),2)
    assert staged['data']['carrier_mc']=='MC-00123'
    assert staged['status']=='REVIEW_REQUIRED'


def test_anchors_are_controls_not_substitute_source_values():
    export=fixture_export([source_row()])
    rows=[normalize(export['rows'][0],2)]
    report=summarize(export,rows,{'total_income':'9999.00','rows':694})
    assert report['total_income']=='1000.10'
    assert set(report['anchor_mismatches'])=={'total_income','rows'}
    assert report['aggregate_margin_percent']=='30.0' and not report['validation_passed']


def test_staged_totals_must_match_authoritative_source():
    export=fixture_export([source_row()])
    staged=normalize(export['rows'][0],2)
    staged['data']['historical_total_expenses']='600.07'
    report=summarize(export,[staged],{})
    assert report['total_expenses']=='600.07'
    assert report['source_financial_totals']['historical_total_expenses']=='700.07'
    assert report['source_to_staged_financial_mismatches']==['historical_total_expenses']
    assert not report['validation_passed']


def test_source_duplicates_are_not_hidden():
    row=source_row()
    changed=source_row(**{'Notes':'DIFFERENT PRIVATE EVIDENCE'})
    export=fixture_export([row,row,changed])
    report=summarize(export,[normalize(r,i+2) for i,r in enumerate(export['rows'])],{})
    assert report['duplicate_rows']==2 and report['identical_duplicate_rows']==1
    assert report['conflicting_duplicate_ids']==1 and not report['validation_passed']


def test_actual_headers_required_before_proposed_mapping():
    export=fixture_export([source_row()])
    proposal=schema_mapping(export)
    assert proposal.status=='PROPOSED' and proposal.columns['Total Expenses']=='historical_total_expenses'
    assert proposal.columns['Exchange Rate Date']=='raw_source.Exchange Rate Date'
    with pytest.raises(ValueError,match='schema_mismatch'):
        schema_mapping({**export,'headers':['Assumed schema']})


def test_alias_and_equipment_proposals_never_merge_raw_labels():
    rows=[normalize(source_row(**{'Load ID':str(i),'Customer':label}),i+2) for i,label in enumerate([
        'Tube Supply','Special Metals Inc. (Tube Supply)','TUBE SUPPLY (Special Metals Inc.)'])]
    raw,aliases,equipment=identities_and_equipment(rows)
    assert len(raw)==3 and len(aliases)==1 and aliases[0].sample_size==3
    assert aliases[0].status=='PROPOSED'
    assert equipment[0].proposed_family=='FLATBED_OR_STEP_DECK' and equipment[0].proposed_length_feet==48
    assert equipment[0].raw_label=="48' Flatbed/Step Deck"


def test_staging_idempotence_version_conflicts_and_historical_only(runtime):
    paths,inbox=runtime
    source=write_source(inbox,[source_row()])
    stager=AscendRealStager(paths)
    first,target=stager.stage(source,anchors={})
    second,_=stager.stage(source,anchors={})
    assert first['validation_passed'] and second['identical_export_already_staged']
    assert first['batch_id']==second['batch_id'] and second['committed_rows']==0
    report=(target/'staging-report.md').read_text(encoding='utf-8')
    assert 'SYNTHETIC PRIVATE' not in report and '832-555' not in report
    assert '2024-09-03' in report and '30.000000' in report
    changed=write_source(inbox,[source_row(**{'Private Notes':'New private evidence'})],'changed.csv')
    conflict,_=stager.stage(changed,anchors={})
    assert conflict['prior_version_conflicts']==1 and not conflict['validation_passed']
    store=Store(paths.path('Data','booking-logistics','history','history.sqlite3'))
    try:
        assert len(store.all('booking-logistics','ascend_stage_batch'))==2
        assert len(store.all('booking-logistics','ascend_stage_row'))==2
        for kind in ['history_record','ascend_history_record','shipment','mail_update_proposal','task']:
            assert not store.all('booking-logistics',kind)
        assert any(row['status']=='REVIEW_REQUIRED' for row in store.all('booking-logistics','ascend_stage_row'))
    finally:
        store.close()
    assert not paths.path('Data','booking-logistics','carrierview.sqlite3').exists()
    assert not paths.path('Data','booking-logistics','mail.sqlite3').exists()


def test_mismatch_stages_quarantine_not_commit(runtime):
    paths,inbox=runtime
    source=write_source(inbox,[source_row()])
    report,_=AscendRealStager(paths).stage(source)  # Real 694-row anchors intentionally fail.
    assert not report['validation_passed'] and report['committed_rows']==0
    assert report['commit_status'].startswith('BLOCKED')


def test_unexpected_currency_or_payment_columns_block_validation():
    export=fixture_export([source_row(**{'Exchange Rate':'1.5'})])
    result=summarize(export,[normalize(export['rows'][0],2)],{})
    assert 'expected_empty:Exchange Rate' in result['anchor_mismatches']
    assert not result['validation_passed']


def test_scoped_note_candidates_are_bounded_unverified_and_private():
    rows=[normalize(source_row(**{'Load ID':str(i),'Notes':'Synthetic QuickPay PRIVATE text'}),i+2) for i in range(8)]
    rows.append(normalize(source_row(**{'Load ID':'99','Customer':'Different Customer','Notes':'QuickPay'}),10))
    review=scoped_note_patterns(rows,'Synthetic Customer',max_loads=4)
    assert review['sample_size']==4 and review['model_calls']==0
    candidate=review['candidates'][0]
    assert candidate['matched_distinct_loads']==4 and not candidate['approved'] and not candidate['applied']
    assert 'PRIVATE' not in str(candidate) and candidate['date_from']=='2024-09-03'
    assert not scoped_note_patterns(rows,'Synthetic Customer',max_loads=2)['candidates']
    with pytest.raises(ValueError):
        scoped_note_patterns(rows,'Synthetic Customer',max_loads=10000)


def test_source_mc_prefixes_and_placeholders_distinguished():
    prefixed=normalize(source_row(**{'Carrier MC Number':'MC001234'}),2)
    assert not prefixed['warnings'] and prefixed['data']['carrier_mc']=='MC001234'
    missing=normalize(source_row(**{'Carrier MC Number':'MC'}),2)
    assert 'Carrier MC Number:prefix_only_numeric_identity_missing' in missing['warnings']
    spaced=normalize(source_row(**{'Carrier USDOT Number':' 000123 '}),2)
    assert spaced['data']['carrier_dot']==' 000123 ' and spaced['warnings']


def test_real_style_lane_count_preserves_raw_whitespace():
    export=fixture_export([source_row(),source_row(**{'Load ID':'43','First Pick City':'Alpha '})])
    report=summarize(export,[normalize(row,i+2) for i,row in enumerate(export['rows'])],{})
    assert report['lane_count']==2 and report['lane_count_trimmed_casefold_proposal']==1
    assert export['rows'][1]['First Pick City']=='Alpha '
