"""M4A inspection/staging only. No commit or operational-service execution path."""
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from pydantic import ValidationError

from app.core.runtime import RuntimePaths
from app.models.ascend_history import (
    AscendHistoricalEvidence, AscendSchemaMapping, HistoricalLocation, ProposedCustomerAliasGroup,
    ProposedEquipmentMapping, RawCustomerIdentity,
)
from app.models.domain import AuditEvent, utcnow
from app.services.history import AscendHistoricalImporter
from app.services.mail_sync import digest
from app.services.store import Store

HEADERS = """Load ID|Pickups|Deliveries|All Stops & Actions|Customer|Carrier|Drivers|Power Unit|Trailer|References|Notes|Private Notes|Load Status|Branch|Invoice Dates|Bill Dates|Users & Roles|Total Income|Total Expenses|Gross Profit/Loss|Gross Profit/Loss %|Equipment|First Pick Name|First Pick Address|First Pick City|First Pick State|First Pick Postal|First Pick Country|First Pick Date|Last Drop Name|Last Drop Address|Last Drop City|Last Drop State|Last Drop Postal|Last Drop Country|Last Drop Date|Client Mileage|Carrier Mileage|Deadhead Mileage|Truck Status|Carrier MC Number|Carrier USDOT Number|Weight|Load Created Date|Invoice Payment Dates|Bill Payment Dates|Invoice Balance|Commodity|Container|Last Free Day|Temperature|Bill Ref #|Last Contact|Manifest|Invoice Sent Date|Total Income (Foreign Currency Amount)|Total Expenses (Foreign Currency Amount)|Exchange Rate|Exchange Rate Date""".split('|')
TEXT_FIELDS = {'raw_customer':'Customer', 'raw_carrier':'Carrier', 'carrier_mc':'Carrier MC Number',
    'carrier_dot':'Carrier USDOT Number', 'raw_equipment':'Equipment', 'commodity':'Commodity',
    'truck_status':'Truck Status', 'drivers':'Drivers', 'power_unit':'Power Unit', 'trailer':'Trailer',
    'references':'References', 'load_status':'Load Status', 'branch':'Branch', 'notes':'Notes',
    'private_notes':'Private Notes'}
NUMBER_FIELDS = {'weight':'Weight', 'client_mileage':'Client Mileage', 'carrier_mileage':'Carrier Mileage'}
MONEY_FIELDS = {'historical_total_income':'Total Income', 'historical_total_expenses':'Total Expenses',
    'historical_gross_profit_loss':'Gross Profit/Loss', 'historical_margin_percent':'Gross Profit/Loss %'}
EXPECTED_EMPTY = ['Invoice Dates','Bill Dates','Users & Roles','Deadhead Mileage','Invoice Payment Dates',
    'Bill Payment Dates','Invoice Balance','Container','Last Free Day','Bill Ref #','Manifest',
    'Invoice Sent Date','Total Income (Foreign Currency Amount)','Total Expenses (Foreign Currency Amount)','Exchange Rate']
ANCHORS = {'rows':694, 'columns':59, 'unique_load_ids':694, 'customers':19, 'carriers':354, 'equipment_labels':14,
    'pickup_date_from':'2024-09-03', 'pickup_date_to':'2026-09-04',
    'created_date_from':'2024-08-28', 'created_date_to':'2026-09-03',
    'total_income':'1693484.10', 'total_expenses':'1378557.00', 'gross_profit_loss':'314927.10',
    'status_distribution':{'Completed':642,'To Be Billed':43,'Delivered':8,'Driver Assigned':1}}


def decimal_value(raw, *, money=False, percent=False):
    value = raw.strip()
    if money and value.startswith('$'):
        value = value[1:]
    if percent and value.endswith('%'):
        value = value[:-1]
    if not re.fullmatch(r'-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?', value):
        raise ValueError('invalid_decimal')
    result = Decimal(value.replace(',', ''))
    if not result.is_finite() or (money and result != result.quantize(Decimal('.01'))):
        raise ValueError('invalid_money_precision')
    return result


def local_date(raw):
    if not raw.strip():
        return None, None
    for pattern in ('%m/%d/%Y %H:%M', '%m/%d/%Y'):
        try:
            parsed = datetime.strptime(raw.strip(), pattern)
            return parsed.date(), parsed if '%H' in pattern else None
        except ValueError:
            continue
    raise ValueError('invalid_local_date')


def schema_mapping(export):
    if export['headers'] != HEADERS:
        raise ValueError('ascend_schema_mismatch')
    columns = {'Load ID':'source_load_id', 'Load Created Date':'created_at',
               **{source:target for target,source in (TEXT_FIELDS | NUMBER_FIELDS | MONEY_FIELDS).items()}}
    for prefix, target in [('First Pick','pickup'),('Last Drop','delivery')]:
        for suffix in ['Name','Address','City','State','Postal','Country','Date']:
            columns[prefix+' '+suffix] = target+'.'+suffix.lower()
    for column in HEADERS:
        columns.setdefault(column, 'raw_source.'+column)
    return AscendSchemaMapping(source_hash=export['source_hash'], source_headers=export['headers'], columns=columns)


def normalize(row, line):
    errors = []
    fields = {'source_load_id':row['Load ID'], **{target:row[source] or None for target,source in TEXT_FIELDS.items()}}
    if not re.fullmatch(r'[0-9]+', row['Load ID']):
        errors.append('Load ID:invalid_identifier')
    for target, source in NUMBER_FIELDS.items():
        try:
            fields[target] = decimal_value(row[source]) if row[source].strip() else None
        except (ValueError, InvalidOperation):
            errors.append(source+':invalid_number')
    for target, source in MONEY_FIELDS.items():
        try:
            fields[target] = decimal_value(row[source], money=target!='historical_margin_percent',
                                           percent=target=='historical_margin_percent')
        except (ValueError, InvalidOperation):
            errors.append(source+':invalid_money')
    for prefix, target in [('First Pick','pickup'),('Last Drop','delivery')]:
        location = {suffix.lower():row[prefix+' '+suffix] or None
                    for suffix in ['Name','Address','City','State','Postal','Country']}
        try:
            day, moment = local_date(row[prefix+' Date'])
            location.update(date=day, local_datetime=moment)
        except ValueError:
            errors.append(prefix+' Date:invalid_date')
        fields[target] = HistoricalLocation(**location)
    try:
        created = datetime.fromisoformat(row['Load Created Date']) if row['Load Created Date'].strip() else None
        if created is not None and (created.tzinfo is None or created.utcoffset() is None):
            raise ValueError()
        fields['created_at'] = created
    except ValueError:
        errors.append('Load Created Date:invalid_date')
    arithmetic, margin = None, None
    if all(target in fields for target in MONEY_FIELDS):
        income, expenses, gross, exported = (fields[target] for target in MONEY_FIELDS)
        arithmetic = income-expenses == gross
        margin = (gross/income*100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) == exported if income else None
        if not arithmetic:
            errors.append('Gross Profit/Loss:arithmetic_mismatch')
        if margin is False:
            errors.append('Gross Profit/Loss %:rounded_margin_mismatch')
        if margin is None:
            errors.append('Gross Profit/Loss %:zero_income_denominator')
    try:
        data = AscendHistoricalEvidence(**fields).model_dump(mode='json')
    except ValidationError:
        data = None
        errors.append('typed_normalization_failed')
    id_warnings = []
    for source in ['Carrier MC Number','Carrier USDOT Number']:
        original = row[source]
        trimmed = original.strip()
        if not trimmed:
            continue
        if original != trimmed:
            id_warnings.append(source+':surrounding_whitespace_preserved')
        if source=='Carrier MC Number' and trimmed=='MC':
            id_warnings.append(source+':prefix_only_numeric_identity_missing')
        elif not re.fullmatch(r'(?:MC)?[0-9]+' if source=='Carrier MC Number' else r'[0-9]+',trimmed):
            id_warnings.append(source+':invalid_identifier_format')
    return {'row':line, 'source_load_id':row['Load ID'], 'evidence_hash':digest(row), 'data':data,
            'raw_source':row, 'errors':errors, 'warnings':id_warnings,
            'arithmetic_pass':arithmetic, 'margin_pass':margin,
            'status':'INVALID' if errors else 'REVIEW_REQUIRED' if id_warnings else 'STAGED'}


def identities_and_equipment(rows):
    customers, equipment = defaultdict(list), Counter()
    for row in rows:
        raw = row['raw_source']
        if raw['Customer']:
            customers[raw['Customer']].append(raw['Load ID'])
        if raw['Equipment']:
            equipment[raw['Equipment']] += 1
    identities = [RawCustomerIdentity(id=digest(['raw_customer',name]),label=name,
                    sample_size=len(set(ids)),source_load_ids=sorted(set(ids))) for name,ids in sorted(customers.items())]
    # Shared distinctive name tokens produce proposals only, never a merged customer identity.
    def tokens(name):
        return set(re.findall(r'[a-z0-9]+',name.casefold())) - {'inc','llc','ltd','co','the','corp'}
    links = []
    for index, left in enumerate(identities):
        for right in identities[index+1:]:
            a,b = tokens(left.label),tokens(right.label)
            if min(len(a),len(b)) >= 2 and (a <= b or b <= a):
                links.append({left.id,right.id})
    groups = []
    for link in links:
        overlap = [group for group in groups if group & link]
        for group in overlap:
            link |= group
            groups.remove(group)
        groups.append(link)
    aliases = []
    for group in groups:
        members = [i for i in identities if i.id in group]
        ids = sorted({load for member in members for load in member.source_load_ids})
        aliases.append(ProposedCustomerAliasGroup(id=digest(sorted(group)),raw_identity_ids=sorted(group),
            raw_labels=[m.label for m in members],reason='Shared distinctive name tokens; relationship requires owner review',
            sample_size=len(ids),source_load_ids=ids))
    proposals = []
    for label,count in sorted(equipment.items()):
        low = label.casefold()
        family = ('FLATBED_OR_STEP_DECK' if 'flatbed' in low and 'step' in low else
                  'FLATBED' if 'flatbed' in low else 'STEP_DECK' if 'step' in low else
                  'REEFER' if 'reefer' in low else 'VAN' if 'van' in low else
                  'HOTSHOT' if 'hotshot' in low else None)
        length = re.search(r"\b(\d{2})\s*['′]",label)
        proposals.append(ProposedEquipmentMapping(raw_label=label,proposed_family=family,
            proposed_length_feet=int(length.group(1)) if length else None,sample_size=count,
            proposed_features=['AIR_RIDE'] if 'air-ride' in low else []))
    return identities,aliases,proposals


def scoped_note_patterns(rows, customer, *, max_loads=50, max_characters=4000):
    """Bounded deterministic review candidates for one raw customer; no model or SOP writes."""
    if not 1<=max_loads<=100 or not 1<=max_characters<=4000:
        raise ValueError('bounded_note_review_required')
    topics = {
        'tracking requirements':r'\btracking\b.{0,80}\b(?:required|requirement|mandatory)\b|\b(?:required|mandatory)\b.{0,80}\btracking\b',
        'POD deadlines':r'\bPOD\b.{0,100}\b(?:within|hours|deadline)\b',
        'loaded pictures':r'\b(?:loaded|loading)\b.{0,60}\b(?:pictures|photos)\b',
        'detention terms':r'\bdetention\b',
        'QuickPay terms':r'\bquick\s*pay\b',
        'customer updates':r'\b(?:update|updates)\b.{0,70}\b(?:required|daily|hourly|customer)\b',
        'facility instructions':r'\b(?:facility|shipper|receiver)\b.{0,70}\b(?:instructions|required|appointment)\b',
    }
    selected = []
    seen = set()
    for row in rows:
        if row['raw_source']['Customer']==customer and row['source_load_id'] not in seen:
            selected.append(row)
            seen.add(row['source_load_id'])
            if len(selected)>=max_loads:
                break
    candidates = []
    for topic,pattern in topics.items():
        evidence = []
        for row in selected:
            for field in ['Notes','Private Notes']:
                text = row['raw_source'][field][:max_characters]
                match = re.search(pattern,text,re.I|re.S)
                if match:
                    evidence.append({'source_load_id':row['source_load_id'],'evidence_hash':row['evidence_hash'],
                                     'source_field':field,'start':match.start(),'end':match.end()})
                    break
        if len(evidence)>=3:
            dates = [row['data']['pickup']['date'] for row in selected if row['data'] and row['data']['pickup']['date'] and
                     any(item['source_load_id']==row['source_load_id'] for item in evidence)]
            candidates.append({'topic':topic,'raw_customer':customer,'matched_distinct_loads':len(evidence),
                'reviewed_sample_size':len(selected),'date_from':min(dates) if dates else None,
                'date_to':max(dates) if dates else None,'evidence':evidence,'status':'PROPOSED_REVIEW_TOPIC',
                'verified_rule':False,'approved':False,'applied':False,
                'limitations':'Keyword evidence may be boilerplate or negated; owner must review exact source before an SOP rule'})
    return {'raw_customer':customer,'sample_size':len(selected),'max_characters_per_field':max_characters,
            'source_order':'first distinct matching loads in CSV order','model_calls':0,'candidates':candidates}


def summarize(export, rows, anchors):
    raw = export['rows']
    good = [row['data'] for row in rows if row['data'] is not None]
    counts = Counter(row['Load ID'] for row in raw)
    completeness = {header:{'populated':sum(bool(row[header].strip()) for row in raw),
                             'missing':sum(not row[header].strip() for row in raw)} for header in export['headers']}
    def coverage(values):
        present = sorted(value for value in values if value)
        return [present[0],present[-1]] if present else [None,None]
    pickup = coverage(d['pickup']['date'] for d in good)
    delivery = coverage(d['delivery']['date'] for d in good)
    created = coverage(d['created_at'][:10] if d['created_at'] else None for d in good)
    sums = {}
    for target,source in MONEY_FIELDS.items():
        if target == 'historical_margin_percent':
            continue
        values = []
        for row in raw:
            try:
                values.append(decimal_value(row[source],money=True))
            except (ValueError,InvalidOperation):
                pass
        sums[target] = sum(values,Decimal(0)) if len(values)==len(raw) else None
    staged_sums = {field:sum((Decimal(d[field]) for d in good),Decimal(0)) if len(good)==len(raw) else None
                   for field in list(MONEY_FIELDS)[:3]}
    financial_mismatches = [field for field in staged_sums if staged_sums[field] != sums[field]]
    income,expenses,gross = (staged_sums[field] for field in list(MONEY_FIELDS)[:3])
    def labels(field):
        return len({row[field] for row in raw if row[field]})
    observed = {'rows':len(raw),'columns':len(export['headers']), 'unique_load_ids':len(counts),
        'customers':labels('Customer'),'carriers':labels('Carrier'),'equipment_labels':labels('Equipment'),
        'pickup_date_from':pickup[0],'pickup_date_to':pickup[1], 'created_date_from':created[0],'created_date_to':created[1],
        'total_income':str(income) if income is not None else None,
        'total_expenses':str(expenses) if expenses is not None else None,
        'gross_profit_loss':str(gross) if gross is not None else None,
        'status_distribution':dict(Counter(row['Load Status'] for row in raw))}
    mismatches = []
    for key,expected in anchors.items():
        actual = observed.get(key)
        matches = Decimal(actual)==Decimal(expected) if key in {'total_income','total_expenses','gross_profit_loss'} and actual else actual==expected
        if not matches:
            mismatches.append(key)
    for header in EXPECTED_EMPTY:
        if completeness[header]['populated']:
            mismatches.append('expected_empty:'+header)
    if completeness['Exchange Rate Date']['populated'] != len(raw):
        mismatches.append('exchange_rate_date_population')
    mismatches.extend('source_to_staged:'+field for field in financial_mismatches)
    duplicates = sum(count-1 for count in counts.values())
    conflicting = sum(len({digest(row) for row in raw if row['Load ID']==load})>1
                      for load,count in counts.items() if count>1)
    identical = sum(count-len({digest(row) for row in raw if row['Load ID']==load})
                    for load,count in counts.items() if count>1)
    lanes = {(r['First Pick City'],r['First Pick State'],r['Last Drop City'],r['Last Drop State']) for r in raw
             if all(r[k] for k in ['First Pick City','First Pick State','Last Drop City','Last Drop State'])}
    trimmed_lanes = {tuple(part.strip().casefold() for part in lane) for lane in lanes}
    identifiers = {}
    for source in ['Carrier MC Number','Carrier USDOT Number']:
        values = [r[source] for r in raw]
        identifiers[source] = {'empty':sum(not v.strip() for v in values),
            'prefix_only':sum(v.strip()=='MC' for v in values),
            'prefixed_digits':sum(bool(re.fullmatch(r'MC[0-9]+',v.strip())) for v in values),
            'digits_only':sum(bool(re.fullmatch(r'[0-9]+',v.strip())) for v in values),
            'surrounding_whitespace':sum(v!=v.strip() for v in values),
            'leading_zero_digits':sum(bool(re.match(r'^(?:MC)?0[0-9]+$',v.strip())) for v in values)}
    errors = Counter(error for row in rows for error in row['errors'])
    return {**observed,'source':'Ascend historical export','source_hash':export['source_hash'],
        'calculated_at':utcnow().isoformat(),'raw_vs_derived':'source labels/counts; financial aggregates and validation are derived',
        'delivery_date_coverage':delivery,'lane_count':len(lanes),'lane_count_anchor_approximate':109,
        'lane_count_difference_from_approximate':len(lanes)-109,
        'lane_count_trimmed_casefold_proposal':len(trimmed_lanes),
        'identifier_format_profile':identifiers,
        'missing_delivery_date_statuses':dict(Counter(r['Load Status'] for r in raw if not r['Last Drop Date'].strip())),
        'rows_with_errors':sum(bool(row['errors']) for row in rows), 'errors_by_field':dict(errors),
        'rows_with_identifier_warnings':sum(bool(row['warnings']) for row in rows),
        'identifier_warning_counts':dict(Counter(w for row in rows for w in row['warnings'])),
        'missing_core_fields':{key:completeness[key]['missing'] for key in ['Load ID','First Pick Date','Last Drop Date',
            'Load Created Date','Total Income','Total Expenses','Gross Profit/Loss','Gross Profit/Loss %']},
        'staged_financial_totals':{key:str(value) if value is not None else None for key,value in staged_sums.items()},
        'source_financial_totals':{key:str(value) if value is not None else None for key,value in sums.items()},
        'source_to_staged_financial_mismatches':financial_mismatches,
        'identical_duplicate_rows':identical,'duplicate_rows':duplicates,
        'conflicting_duplicate_ids':conflicting,'anchor_mismatches':mismatches,
        'arithmetic_rows_passed':sum(row['arithmetic_pass'] is True for row in rows),
        'margin_rows_passed':sum(row['margin_pass'] is True for row in rows),
        'aggregate_margin_percent':str(gross/income*100) if gross is not None and income else None,
        'currency':'UNCONFIRMED_DOLLAR_UNIT','historical_carrier_pay':None,
        'field_completeness':completeness,'fully_empty_columns':[k for k,v in completeness.items() if not v['populated']],
        'local_datetime_counts':{key:sum(d[key]['local_datetime'] is not None for d in good) for key in ['pickup','delivery']},
        'validation_passed':not mismatches and not errors and not duplicates,
        'commit_status':'BLOCKED_PENDING_OWNER_MAPPING_AND_SEMANTICS_APPROVAL', 'committed_rows':0}


class AscendRealStager:
    def __init__(self, paths=None):
        self.paths = paths or RuntimePaths.from_environment()

    def inspect(self, source):
        # Read and validate the actual file before constructing the proposed mapping.
        export = AscendHistoricalImporter.read_export(source)
        mapping = schema_mapping(export)
        if any(None in row or any(value is None for value in row.values()) for row in export['rows']):
            raise ValueError('ascend_row_width_mismatch')
        rows = [normalize(row,index+2) for index,row in enumerate(export['rows'])]
        return export,mapping,rows

    def stage(self, source, *, anchors=None):
        export,mapping,rows = self.inspect(source)
        report = summarize(export,rows,ANCHORS if anchors is None else anchors)
        identities,aliases,equipment = identities_and_equipment(rows)
        report.update(source_identifier=source.name,customer_identities=[i.model_dump() for i in identities],
                      proposed_customer_aliases=[a.model_dump() for a in aliases],
                      proposed_equipment=[p.model_dump() for p in equipment],mapping=mapping.model_dump())
        if identities:
            customer = max(identities,key=lambda identity:identity.sample_size).label
            report['scoped_note_review'] = scoped_note_patterns(rows,customer)
        batch_id = digest([export['source_hash'],mapping.model_dump()])
        path = self.paths.path('Data','booking-logistics','history','history.sqlite3')
        store = Store(path)
        try:
            with store.transaction():
                batches = store.all('booking-logistics','ascend_stage_batch')
                previous = next((batch for batch in batches if batch['id']==batch_id),None)
                if previous:
                    report['first_staged_at'] = previous['report'].get('first_staged_at',previous['report']['calculated_at'])
                else:
                    report['first_staged_at'] = report['calculated_at']
                existing = store.all('booking-logistics','ascend_stage_row')
                by_id = defaultdict(set)
                for old in existing:
                    by_id[old['source_load_id']].add(old['evidence_hash'])
                # Include committed historical evidence if a later authorized implementation adds it.
                for old in store.all('booking-logistics','ascend_history_record'):
                    by_id[old['source_load_id']].add(old['evidence_hash'])
                for old in store.all('booking-logistics','history_record'):
                    if old.get('provenance',{}).get('source_system') == 'ascend_export':
                        by_id[old['data']['load_number']].add('legacy_evidence_requires_reconciliation')
                conflicts = [row for row in rows if by_id[row['source_load_id']] and
                             row['evidence_hash'] not in by_id[row['source_load_id']]]
                for row in conflicts:
                    row['warnings'].append('prior_source_version_conflict')
                    row['status'] = 'REVIEW_REQUIRED'
                report.update(batch_id=batch_id, identical_export_already_staged=previous is not None,
                              prior_version_conflicts=len(conflicts))
                if conflicts:
                    report['validation_passed'] = False
                for row in rows:
                    row_id = digest([batch_id,row['row'],row['evidence_hash']])
                    store.put('booking-logistics','ascend_stage_row',row_id,{'batch_id':batch_id,**row})
                # Stage/quarantine only. This module has no commit endpoint or scheduler coupling.
                store.put('booking-logistics','ascend_stage_batch',batch_id,{'id':batch_id,
                    'source_hash':export['source_hash'],'source_identifier':source.name,
                    'mapping':mapping.model_dump(),'status':'STAGED_REVIEW_REQUIRED' if report['validation_passed'] else 'QUARANTINED',
                    'row_count':len(rows),'report':report})
                store.audit(AuditEvent(tenant_id='booking-logistics',source='ascend_historical_csv',actor_id='FreightDesk/Avery',
                    event='ASCEND_HISTORY_STAGED',explanation='Historical staging only; mapping approval required before commit',
                    facts={'rows':len(rows),'validation_passed':report['validation_passed'],
                           'identical_export':previous is not None,'version_conflicts':len(conflicts)}))
        finally:
            store.close()
        target = self.paths.path('Data','booking-logistics','history','reports',batch_id)
        target.mkdir(parents=True,exist_ok=True)
        (target/'staging-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        (target/'proposed-mapping.json').write_text(mapping.model_dump_json(indent=2),encoding='utf-8')
        (target/'staging-report.md').write_text(render_report(report),encoding='utf-8')
        return report,target


def safe_label(value):
    value = re.sub(r'https?://\S+|[\w.+-]+@[\w.-]+','[redacted]',str(value))
    value = re.sub(r'(?<!\w)\+?\d[\d ()-]{7,}\d','[redacted]',value)
    return value.replace('|','\\|').replace('\n',' ').replace('\r',' ')[:200]


def render_report(report):
    rows = ['# Ascend historical staging review','',
        'Status: staged only; real historical commit requires owner approval.',
        'Source: '+safe_label(report['source_identifier']), 'SHA-256: '+report['source_hash'],
        'Calculated at: '+report['calculated_at'],'',
        'All aggregate results below are derived from the CSV. Raw labels remain distinct. No current-market pricing claims.',
        'Raw private notes, driver details, addresses and record payloads are omitted from this report.','',
        '| Measure | Observed |','|---|---|']
    for key in ['rows','columns','unique_load_ids','pickup_date_from','pickup_date_to','created_date_from',
                'created_date_to','customers','carriers','lane_count','equipment_labels','rows_with_errors',
                'rows_with_identifier_warnings','duplicate_rows','conflicting_duplicate_ids','prior_version_conflicts',
                'total_income','total_expenses','gross_profit_loss','aggregate_margin_percent','arithmetic_rows_passed',
                'margin_rows_passed','validation_passed','committed_rows']:
        value = str(report[key])  # Only computed counts, numeric totals and validated ISO dates in this fixed list.
        if key=='aggregate_margin_percent' and report[key] is not None:
            value = format(Decimal(report[key]),'.6f')
        rows.append('| '+key.replace('_',' ')+' | '+value+' |')
    rows += ['', 'Amounts use the source dollar unit; ISO currency awaits owner confirmation. Total Expenses is',
        'historical_total_expenses, not historical_carrier_pay. Margin = gross / income × 100; row check uses',
        'two decimal percentage points with ROUND_HALF_UP. Aggregate margin is a ratio of sums, not an average of row percentages.',
        '', '## Validation issues','', 'Anchor mismatches: '+safe_label(report['anchor_mismatches']),
        'Field errors: '+str(report['errors_by_field']),
        'Source-to-staged financial mismatches: '+str(report['source_to_staged_financial_mismatches']),
        'Identifier warnings: '+str(report['identifier_warning_counts']),
        'Missing core fields (retained as unknown; owner review required): '+str(report['missing_core_fields']),
        'Missing delivery-date source statuses: '+str(report['missing_delivery_date_statuses']),
        'Lane count uses exact nonblank first/final city/state tuples; the supplied 109 anchor was approximate.',
        'Delivery-date coverage: '+' to '.join(str(value) for value in report['delivery_date_coverage'])+'.',
        'Time-bearing pickup/delivery rows: '+str(report['local_datetime_counts'])+'; remaining populated values are date-only.',
        'Trim/casefold lane-count proposal: '+str(report['lane_count_trimmed_casefold_proposal'])+' (raw lane values remain unchanged).',
        'Identifier representation profile: '+str(report['identifier_format_profile']),
        'MC-prefixed digits are a valid source representation, retained exactly. Literal MC has no numeric identity; blank identifiers remain missing.',
        'Pickup/delivery local dates may include time; no timezone is supplied. Source Load Created Date retains its explicit offset.',
        'Exchange Rate Date is raw metadata only and is not used for dates, payments, financial events or FX calculations.',
        '', '## Source status distribution','', '| Raw status | Rows |','|---|---|']
    rows += ['| '+safe_label(k)+' | '+str(v)+' |' for k,v in report['status_distribution'].items()]
    rows += ['', '## Proposed schema mapping','', 'All 59 source columns are preserved in private raw_source evidence.',
        'First Pick and Last Drop do not describe all intermediate stops. Raw Pickups/Deliveries/All Stops & Actions are retained.',
        'MC/DOT and postal values stay strings, including leading zeros. Empty fields remain empty/unknown.',
        '', '| Source column | Proposed typed target or raw metadata |','|---|---|']
    rows += ['| '+safe_label(k)+' | '+safe_label(v)+' |' for k,v in report['mapping']['columns'].items()]
    rows += ['', '## Field completeness','', '| Column | Populated | Missing |','|---|---|---|']
    rows += ['| '+safe_label(k)+' | '+str(v['populated'])+' | '+str(v['missing'])+' |' for k,v in report['field_completeness'].items()]
    rows += ['', '## Raw customer identities','', '| Raw label | Distinct loads |','|---|---|']
    rows += ['| '+safe_label(i['label'])+' | '+str(i['sample_size'])+' |' for i in report['customer_identities']]
    rows += ['', '## Proposed customer aliases','', 'No identity has been merged or approved. Name similarity is only review evidence.']
    for group in report['proposed_customer_aliases']:
        rows += ['', ', '.join(safe_label(n) for n in group['raw_labels'])+': '+str(group['sample_size'])+' distinct loads. '+group['reason']]
    rows += ['', '## Proposed equipment normalization','', '| Raw label | Proposed family | Length ft | Features | Rows |','|---|---|---|---|---|']
    rows += ['| '+safe_label(e['raw_label'])+' | '+str(e['proposed_family'] or 'REVIEW_REQUIRED')+' | '+
             str(e['proposed_length_feet'] or 'Unknown')+' | '+', '.join(e['proposed_features'])+' | '+str(e['sample_size'])+' |' for e in report['proposed_equipment']]
    note_review = report.get('scoped_note_review')
    if note_review:
        rows += ['', '## Bounded recurring-note review','',
            'Raw customer: '+safe_label(note_review['raw_customer'])+'. Reviewed first '+str(note_review['sample_size'])+
            ' distinct source-order loads; up to '+str(note_review['max_characters_per_field'])+' characters per Notes/Private Notes field.',
            'Model calls: 0. Candidate topics are unverified keyword evidence, possibly boilerplate or negated. No SOP rule is approved or applied.',
            '', '| Candidate topic | Distinct matching loads | Sample size | Pickup-date coverage |','|---|---|---|---|']
        rows += ['| '+candidate['topic']+' | '+str(candidate['matched_distinct_loads'])+' | '+
                 str(candidate['reviewed_sample_size'])+' | '+str(candidate['date_from'])+' to '+str(candidate['date_to'])+' |'
                 for candidate in note_review['candidates']]
    rows += ['', '## Approval required before commit','',
        '1. Approve this source hash and proposed mapping, retaining all raw labels and multi-stop evidence.',
        '2. Confirm the source monetary currency (proposed USD) and retain Total Expenses as total expenses, not carrier pay.',
        '3. Approve local pickup/delivery date/time preservation with unknown timezone; keep Exchange Rate Date as raw-only metadata.',
        '4. Approve retaining missing delivery dates, missing/prefix-only MC values and identifier whitespace as explicit raw-data limitations, or choose row exclusions. No identifier number will be invented. Anchor/arithmetic failures remain blocked.',
        '5. Authorize historical-only commit to history.sqlite3. No canonical shipment, mail proposal, scheduler or vendor writes.',
        '', 'Customer alias and equipment proposals may remain unapproved and separate. They are not prerequisites for a raw-preserving commit.',
        'No notes corpus was sent to a model. Post-commit profiles and actual SOP-rule approval remain pending; no rules were approved or applied.']
    return '\n'.join(rows)+'\n'
