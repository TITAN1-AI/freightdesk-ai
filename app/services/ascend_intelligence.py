"""Deterministic, traceable summaries of committed internal history, never market rates."""
import json
from collections import defaultdict
from decimal import Decimal

from app.models.domain import utcnow
from app.services.ascend_commit import TENANT, AscendHistoricalCommitter
from app.services.ascend_staging import HEADERS, safe_label, scoped_note_patterns, summarize
from app.services.mail_sync import digest


def distribution(values):
    values = sorted(Decimal(v) for v in values if v is not None)
    if not values:
        return {'n': 0, 'sum': None, 'min': None, 'p25': None, 'median': None, 'p75': None,
                'max': None, 'mean': None, 'negative': 0, 'zero': 0}
    def quantile(fraction):
        position = Decimal(len(values)-1)*fraction
        low = int(position)
        return values[low]+(values[min(low+1, len(values)-1)]-values[low])*(position-low)
    return {'n': len(values), 'sum': str(sum(values)), 'min': str(values[0]),
        'p25': str(quantile(Decimal('.25'))), 'median': str(quantile(Decimal('.5'))),
        'p75': str(quantile(Decimal('.75'))), 'max': str(values[-1]),
        'mean': str(sum(values)/len(values)), 'negative': sum(v < 0 for v in values),
        'zero': sum(v == 0 for v in values)}


def build_intelligence(receipt, records):
    now = utcnow().isoformat()
    evidence_sets = {}

    def context(selected):
        selected = sorted({r['id']: r for r in selected}.values(), key=lambda r: r['id'])
        evidence_id = digest([r['id'] for r in selected])
        evidence_sets[evidence_id] = [{'record_id': r['id'], 'source_load_id': r['source_load_id'],
            'source_row': r['row'], 'evidence_hash': r['evidence_hash'], **r['provenance']} for r in selected]
        dates = sorted(r['data']['pickup']['date'] for r in selected if r['data']['pickup']['date'])
        return {'sample_size': len(selected), 'date_from': dates[0] if dates else None,
            'date_to': dates[-1] if dates else None, 'date_basis': 'raw pickup local calendar date, timezone unknown',
            'missing_pickup_dates': len(selected)-len(dates), 'evidence_set': evidence_id,
            'source_hash': receipt['source_hash'], 'batch_id': receipt['batch_id'],
            'calculated_at': now, 'raw_vs_derived': 'raw grouping labels; derived counts and statistics',
            'currency': 'USD', 'currency_basis': 'owner confirmation; staged source currency remains unknown'}

    def stats(selected):
        result = {field: distribution(r['data'][field] for r in selected) for field in [
            'historical_total_income', 'historical_total_expenses', 'historical_gross_profit_loss',
            'historical_margin_percent']}
        income = Decimal(result['historical_total_income']['sum'] or '0')
        gross = Decimal(result['historical_gross_profit_loss']['sum'] or '0')
        result['aggregate_margin_percent'] = str(gross/income*100) if income else None
        return result

    def groups(key):
        grouped = defaultdict(list)
        for row in records:
            grouped[key(row)].append(row)
        return sorted(grouped.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))

    def profiles(kind, key):
        return [{'type': kind, 'raw_identity': identity, 'context': context(rows),
                 'distributions': stats(rows)} for identity, rows in groups(key) if identity]

    customers = profiles('CustomerProfile', lambda r: r['data']['raw_customer'])
    carriers = profiles('CarrierProfile', lambda r: r['data']['raw_carrier'])
    lanes = profiles('LaneProfile', lambda r: tuple(r['data'][stop][part]
        for stop in ['pickup', 'delivery'] for part in ['city', 'state']))
    equipment = profiles('EquipmentUsage', lambda r: r['data']['raw_equipment'])
    facilities = defaultdict(list)
    roles = defaultdict(lambda: defaultdict(int))
    for row in records:
        for role in ['pickup', 'delivery']:
            loc = row['data'][role]
            # Exact address participates in identity privately; never included in the report label.
            identity = tuple(loc[k] for k in ['name', 'address', 'city', 'state', 'postal', 'country'])
            if any(identity):
                facilities[identity].append(row)
                roles[identity][role] += 1
    facility_profiles = []
    for identity, selected in facilities.items():
        facility_profiles.append({'type': 'FacilityProfile', 'facility_id': digest(identity),
            'raw_display_label': [identity[0], identity[2], identity[3], identity[5]],
            'context': context(selected), 'endpoint_observations': dict(roles[identity]),
            'identity_basis': 'exact raw name/address/city/state/postal/country; no geocoding or merging'})
    facility_profiles.sort(key=lambda p: (-p['context']['sample_size'], p['facility_id']))
    patterns = []
    for customer, selected in groups(lambda r: r['data']['raw_customer']):
        review = scoped_note_patterns(selected, customer)
        for candidate in review['candidates']:
            ids = {e['source_load_id'] for e in candidate['evidence']}
            patterns.append({**candidate, 'context': context(selected[:50]),
                'matched_context': context([r for r in selected if r['source_load_id'] in ids]),
                'max_characters_per_field': 4000, 'sampling': 'first 50 distinct loads in CSV order'})
    source_validation = summarize({'headers': HEADERS, 'rows': [r['raw_source'] for r in records],
                                  'source_hash': receipt['source_hash']}, records, {})
    # Do not carry the staging-only status into a committed report.
    for key in ['commit_status', 'committed_rows', 'currency', 'calculated_at', 'raw_vs_derived']:
        source_validation.pop(key, None)
    return {'title': 'Booking Logistics historical intelligence — M4A',
        'scope': 'Internal historical USD values only; NOT current market rates or customer quotes',
        'context': context(records), 'validation': source_validation,
        'CustomerProfile': customers, 'LaneProfile': lanes, 'CarrierProfile': carriers,
        'FacilityProfile': facility_profiles, 'EquipmentUsage': equipment,
        'UnassignedIdentityEvidence': [{'field': field, 'context': context(missing)}
            for field in ['raw_customer', 'raw_carrier', 'raw_equipment']
            if (missing := [r for r in records if not r['data'][field]])],
        'RateHistorySummary': {'type': 'RateHistorySummary', 'context': context(records),
            'distributions': stats(records), 'basis': 'historical customer revenue and total expenses; carrier pay unknown'},
        'candidate_customer_patterns': patterns, 'evidence_sets': evidence_sets,
        'definitions': {'quantiles': 'linear interpolation at (n-1)*p; Decimal arithmetic',
            'margin': 'exported row percentage points; aggregate margin is ratio of sums, not mean row margin',
            'facilities': 'first pickup and last delivery endpoints only; distinct loads and endpoint observations differ',
            'counts': 'exact raw identities, no alias/equipment normalization; lane is raw first/final city/state',
            'patterns': 'unverified keyword topics may be boilerplate or negated; no SOP rules approved or applied'}}


def render_intelligence(report):
    c = report['context']
    lines = ['# '+report['title'], '', report['scope'], '',
        'Calculated at: '+c['calculated_at'], 'Source SHA-256: '+c['source_hash'],
        'Batch: '+c['batch_id'], '',
        'Every table row inherits this timestamp, source hash and batch. Its n, pickup-date range and evidence ID',
        'identify its exact sample; evidence IDs resolve to source rows, immutable records and hashes in historical-intelligence.json.',
        'Labels are raw source evidence; all counts, financial aggregates, distributions and candidate patterns are derived.',
        'USD is owner-confirmed. Total expenses are not carrier pay. Dates have unknown local timezones.',
        'Customer aliases and all equipment mappings remain proposals. Missing delivery evidence stays unverified.',
        'Exchange Rate Date is excluded from date coverage. No live shipment state or vendor was changed.', '',
        '## Full sample and reconciliation', '',
        f"n={c['sample_size']}; pickup dates {c['date_from']} through {c['date_to']}; evidence `{c['evidence_set']}`.", '',
        'The validation object in the JSON contains source-versus-committed totals, arithmetic, dates, missing fields and raw identity counts.',
        'Full-sample statistics below share this context. Financial distributions use linear interpolated quartiles.', '',
        '| Measure | Value |', '|---|---|']
    for key in ['rows', 'unique_load_ids', 'customers', 'carriers', 'lane_count', 'equipment_labels',
                'total_income', 'total_expenses', 'gross_profit_loss', 'aggregate_margin_percent',
                'arithmetic_rows_passed', 'margin_rows_passed', 'delivery_date_coverage', 'missing_delivery_date_statuses']:
        lines.append(f"| {key} | {report['validation'][key]} |")
    lines += [f"| exact endpoint facility identities | {len(report['FacilityProfile'])} |", '',
        '## Full-sample historical financial distributions', '',
        '| Historical measure | n | Minimum | P25 | Median | P75 | Maximum | Mean |', '|---|---|---|---|---|---|---|---|']
    for key, value in report['RateHistorySummary']['distributions'].items():
        if isinstance(value, dict):
            lines.append('| '+key+' | '+' | '.join(str(value[k]) for k in ['n','min','p25','median','p75','max','mean'])+' |')
    for kind, title in [('CustomerProfile', 'Customers by historical load count'), ('LaneProfile', 'Top lanes'),
                        ('CarrierProfile', 'Most-used carriers'), ('EquipmentUsage', 'Most-used raw equipment')]:
        lines += ['', '## '+title, '',
            'All customer/equipment groups are shown; lanes and carriers show the first 20 by load count. Full profiles are in JSON.', '',
            '| Raw identity | n | Pickup date range | Income median USD | Total expenses median USD | GP median USD | Margin median % | Evidence |',
            '|---|---|---|---|---|---|---|---|']
        profiles = report[kind] if kind in ['CustomerProfile','EquipmentUsage'] else report[kind][:20]
        for p in profiles:
            ctx, d = p['context'], p['distributions']
            label = p['raw_identity']
            if isinstance(label, (list, tuple)):
                label = ' / '.join(str(v or '(missing)') for v in label)
            lines.append('| '+safe_label(label)+f" | {ctx['sample_size']} | {ctx['date_from']}–{ctx['date_to']} | "+
                ' | '.join(str(d[k]['median']) for k in ['historical_total_income', 'historical_total_expenses',
                    'historical_gross_profit_loss', 'historical_margin_percent'])+f" | `{ctx['evidence_set']}` |")
    lines += ['', '## Missing raw identities', '',
        'Missing identities are excluded from named profiles and retained in every full-sample financial control.', '',
        '| Missing field | n | Pickup date range | Evidence |', '|---|---|---|---|']
    for missing in report['UnassignedIdentityEvidence']:
        ctx = missing['context']
        lines.append(f"| {missing['field']} | {ctx['sample_size']} | {ctx['date_from']}–{ctx['date_to']} | `{ctx['evidence_set']}` |")
    for field in ['historical_total_income', 'historical_total_expenses',
                  'historical_gross_profit_loss', 'historical_margin_percent']:
        lines += ['', '## Customer distributions: '+field, '',
            'USD amounts; margin uses percentage points. Each row shares its exact CustomerProfile evidence context.', '',
            '| Raw customer | n | Pickup date range | Minimum | P25 | Median | P75 | Maximum | Evidence |',
            '|---|---|---|---|---|---|---|---|---|']
        for p in report['CustomerProfile']:
            ctx, values = p['context'], p['distributions'][field]
            lines.append('| '+safe_label(p['raw_identity'])+
                f" | {values['n']} | {ctx['date_from']}–{ctx['date_to']} | "+
                ' | '.join(str(values[k]) for k in ['min','p25','median','p75','max'])+f" | `{ctx['evidence_set']}` |")
    lines += ['', '## Recurring facilities — top 20', '',
        'Exact endpoint identities include private raw addresses. Display labels can coincide; the facility ID distinguishes them.', '',
        '| Raw display label | Facility ID | Distinct loads n | Pickup / delivery observations | Pickup date range | Evidence |',
        '|---|---|---|---|---|---|']
    for p in report['FacilityProfile'][:20]:
        ctx = p['context']
        lines.append('| '+safe_label(' / '.join(str(v or '(missing)') for v in p['raw_display_label']))+
            f" | `{p['facility_id']}` | {ctx['sample_size']} | {p['endpoint_observations']} | {ctx['date_from']}–{ctx['date_to']} | `{ctx['evidence_set']}` |")
    lines += ['', '## Candidate customer operational topics', '',
        'Deterministic keyword review of first 50 distinct source-order loads per raw customer, up to 4000 characters per note field.',
        'These are review candidates, not confirmed SOPs; keywords can be boilerplate or negated. No raw notes are displayed.', '',
        '| Raw customer / topic | Matching loads | Reviewed n | Reviewed pickup range | Matched pickup range | Reviewed / matched evidence |',
        '|---|---|---|---|---|---|']
    for p in report['candidate_customer_patterns']:
        c, m = p['context'], p['matched_context']
        lines.append('| '+safe_label(p['raw_customer']+' / '+p['topic'])+
            f" | {m['sample_size']} | {c['sample_size']} | {c['date_from']}–{c['date_to']} | {m['date_from']}–{m['date_to']} | `{c['evidence_set']}` / `{m['evidence_set']}` |")
    return '\n'.join(lines)+'\n'


def write_intelligence(committer: AscendHistoricalCommitter, batch_id):
    receipt, records = committer.read_committed(batch_id)
    report = build_intelligence(receipt, records)
    target = committer.paths.path('Data', TENANT, 'history', 'reports', batch_id)
    target.mkdir(parents=True, exist_ok=True)
    (target/'historical-intelligence.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (target/'historical-intelligence.md').write_text(render_intelligence(report), encoding='utf-8')
    return report, target
