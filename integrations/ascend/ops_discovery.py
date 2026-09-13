"""Owner-executed dated operating board discovery. No historical-load fallback or writes."""
import asyncio
import json
import re
from datetime import date, timedelta

from app.core.config import ROOT
from app.core.runtime import RuntimePaths
from app.models.domain import ActionPolicy, utcnow
from app.policies.engine import PolicyEngine
from app.services.ascend_live import local_records
from app.services.live_ops import OpsCandidate, OpsFact, OpsReadGrant, TENANT, build_manifest, owner_report
from app.services.store import Store
from integrations.ascend.field_discovery import LABELS, SCAN, ReadOnly1752Executor
from integrations.ascend.identity import IdentityConfig, observe_session
from integrations.ascend.models import AscendError
from integrations.ascend.board_dates import local_date
from integrations.ascend.ops_board import (ACTIVE_LOADS, FIELDS, HEADERS, SCAN as BOARD, board_evidence,
                                           coverage, select_grid)
from integrations.ascend.session_continuity import checked_browser, owner_login_page, save_report

ORIGIN = 'https://ascendtms.com'
OPS_LABELS = LABELS | {'Driver Phone':'driver_phone', 'Dispatcher':'dispatcher',
    'Pickup Date':'pickup_date', 'Delivery Date':'delivery_date', 'Truck Status':'truck_status',
    'Tracking Status':'tracking_status', 'Stop Count':'stop_count',
    'Pickup Address':'pickup_address', 'Pickup Company':'pickup_company', 'Pickup Start':'pickup_start',
    'Pickup End':'pickup_end', 'Delivery Address':'delivery_address', 'Delivery Company':'delivery_company',
    'Delivery Start':'delivery_start', 'Delivery End':'delivery_end'}
STOP_GROUPS = r'''() => {
    const out = [];
    for (const group of document.querySelectorAll('fieldset,[role="group"]')) {
        const name = (group.getAttribute('aria-label') || group.querySelector('legend')?.textContent || '').trim();
        if (!/^Stop \d+$/.test(name) || !group.getClientRects().length) continue;
        const stop = {sequence:Number(name.split(' ')[1])};
        for (const control of group.querySelectorAll('input:not([type="hidden"]),select')) {
            const label = (control.getAttribute('aria-label') || control.labels?.[0]?.textContent || '').trim();
            const key = {'Stop Type':'type','Address':'address','Company':'company',
                         'Appointment Start':'dateFrom','Appointment End':'dateTo'}[label];
            if (!key || !control.getClientRects().length) continue;
            if (key in stop) {stop.ambiguous=true; continue;}
            stop[key] = control.tagName === 'SELECT' ? control.selectedOptions[0]?.textContent?.trim() : control.value;
        }
        out.push(stop);
        if (out.length>100) return [];
    }
    return out;
}'''


def select_board(rows, service_date, date_format='ISO'):
    selected, unknown_dates = {}, 0
    for row in rows:
        if not re.fullmatch(r'\d{1,20}', row.get('load_number','')):
            raise AscendError('board_load_identity_unrecognized')
        pickup, delivery = local_date(row.get('pickup_date'),date_format), local_date(row.get('delivery_date'),date_format)
        unknown_dates += int(pickup is None or delivery is None)
        if service_date not in {pickup, delivery}:
            continue
        number = row['load_number']
        if number in selected and selected[number] != row:
            raise AscendError('board_duplicate_identity_conflict')
        selected[number] = row
    if len(selected) > 30:
        raise AscendError('ops_candidate_bound_exceeded')
    return selected, unknown_dates


async def read_candidate(page, load_number, authorized_loads, board_row, service_date, running, attempt_id, date_format='ISO', *, active_only=False, progress=None, diagnostic=None):
    progress=progress or (lambda stage:None)
    progress('active_loads_refresh')
    executor = ReadOnly1752Executor(page, running, load_number=load_number, authorized_loads=authorized_loads)
    await executor.navigate_loads()
    if active_only:
        progress('active_loads_view_selection')
        await select_active_loads_view(executor)
    progress('load_detail_open')
    await executor.open_1752()  # Closed exact-load operation, now bound to the discovered identity.
    async def snapshot(section):
        if diagnostic:
            diagnostic('SECTION_FOUND',section)
        progress('detail_identity_verification')
        frame, _ = await executor.detail_identity()
        if diagnostic:
            diagnostic('LOAD_IDENTITY_VERIFIED',section)
        progress('field_contract_extraction')
        labels = OPS_LABELS if not active_only else {k:v for k,v in OPS_LABELS.items() if v not in
            {'customer_revenue','total_expenses','gross_profit','gross_margin','commodity','weight'}} | {
                'Carrier Assigned':'carrier_assigned','Dispatcher Email':'dispatcher_email','Reference':'reference',
                'Pick Date':'pickup_date','Drop Date':'delivery_date','Power Unit':'truck'}
        scanned = await frame.evaluate(SCAN, {'labels':labels, 'identityOnly':False})
        if scanned['overflow'] or scanned != await frame.evaluate(SCAN, {'labels':labels, 'identityOnly':False}):
            raise AscendError('ops_detail_changed_or_exceeded_bound')
        notes = await frame.evaluate('''() => {
            const found = [...document.querySelectorAll('textarea')].filter(e=> e.getClientRects().length &&
                /^(Private Notes|Notes)$/.test((e.getAttribute('aria-label') || e.labels?.[0]?.textContent || '').trim()));
            return found.length ? found.some(e=>!!e.value.trim()) : null;
        }''')
        progress('stop_appointment_extraction')
        return {'rows':[r | {'section':section} for r in scanned['fields']], 'notes':notes,
                'groups':await frame.evaluate(STOP_GROUPS)}
    snapshots = [await snapshot('Current detail')]
    for name, tab in await executor.sections():
        if active_only and name == 'Financials':
            continue
        if await tab.get_attribute('aria-selected') == 'true':
            continue
        await executor.inspect_section(name,tab)
        snapshots.append(await snapshot(name))
    progress('driver_contact_extraction')
    rows = [r for s in snapshots for r in s['rows']]
    facts = {}
    now = utcnow()
    for key in {r['field'] for r in rows if r['field']}:
        matches = [r for r in rows if r['field'] == key]
        same_values = len({r['raw'] for r in matches}) == 1
        unique_per_section = all(sum(r['section'] == section for r in matches) == 1 for section in {r['section'] for r in matches})
        verified = same_values and unique_per_section and matches[0]['raw'] is not None
        facts[key] = OpsFact(value=matches[0]['raw'] if verified else None, source='AscendTMS', observed_at=now,
            source_reference=attempt_id+':detail:'+load_number+':'+matches[0]['label'], verified=verified)
    progress('per_load_reconciliation')
    if not facts.get('load_number') or not facts['load_number'].verified or facts['load_number'].value.strip() != load_number:
        raise AscendError('ops_detail_load_mismatch')
    # A list date is a provider fact, not proof of the detail appointment or timezone.
    for kind in ('pickup','delivery'):
        key = kind+'_date'
        raw = board_row.get(key)
        if facts.get(key) and local_date(facts[key].value,date_format) != local_date(raw,date_format):
            raise AscendError('ops_list_detail_date_conflict')
        if key not in facts and raw:
            facts[key] = OpsFact(value=raw, source='AscendTMS', observed_at=now,
                source_reference=attempt_id+':board:'+load_number+':'+key, verified=True)
    observed_notes = [s['notes'] for s in snapshots if s['notes'] is not None]
    notes = any(observed_notes) if observed_notes else None
    stops = []
    group_snapshots = [s['groups'] for s in snapshots if s['groups']]
    grouped = group_snapshots[0] if group_snapshots and all(g == group_snapshots[0] for g in group_snapshots) else []
    total = facts['stop_count'].value if facts.get('stop_count') else None
    if (total and total.isdigit() and 2 <= int(total) <= 100 and len(grouped) == int(total) and
            {s['sequence'] for s in grouped} == set(range(1,int(total)+1))):
        for stop in sorted(grouped, key=lambda s:s['sequence']):
            stop_type = {'Pickup':'pickup', 'Delivery':'destination', 'Destination':'destination'}.get(stop.get('type'))
            if stop_type and not stop.get('ambiguous') and all(stop.get(k) for k in ('address','company','dateFrom','dateTo')):
                stops.append({**stop, 'type':stop_type, 'verified':True,
                              'source_reference':attempt_id+':detail:'+load_number+':stop-group'})
    # Never infer a two-stop route from two visible addresses. Explicit provider stop count required.
    if not group_snapshots and facts.get('stop_count') and facts['stop_count'].value == '2':
        for kind, stop_type in [('pickup','pickup'),('delivery','destination')]:
            required = [kind+'_'+suffix for suffix in ('address','company','start','end')]
            if all(k in facts and facts[k].verified and facts[k].value for k in required):
                stops.append({'type':stop_type, 'address':facts[required[0]].value, 'company':facts[required[1]].value,
                    'dateFrom':facts[required[2]].value, 'dateTo':facts[required[3]].value, 'verified':True,
                    'source_reference':attempt_id+':detail:'+load_number})
    await executor.guard()
    return OpsCandidate(load_number=load_number, service_date=service_date, identity_verified=True,
        pickup_due=local_date(board_row.get('pickup_date'),date_format) == service_date,
        delivery_due=local_date(board_row.get('delivery_date'),date_format) == service_date, facts=facts,
        notes_present=notes, stops=stops, additional_stops_verified=bool(total and total.isdigit() and len(stops) == int(total)))


def board_candidates(grid, service_date, date_format, attempt_id):
    """Board facts stay private; same-row identity/date proof is sufficient for queue membership only."""
    aliases = {'load_id':'load_number','load_status':'status','pick_date':'pickup_date',
               'drop_date':'delivery_date','power_unit':'truck'}
    rows = [{**r,'load_number':r['load_id'],'pickup_date':r['pick_date'],'delivery_date':r['drop_date']}
            for r in grid['rows']]
    selected, _ = select_board(rows, service_date, date_format)
    if len(rows) != len(selected):
        raise AscendError('board_duplicate_identity_conflict')
    now = utcnow()
    candidates = []
    for number, row in selected.items():
        facts = {}
        for field in FIELDS:
            fact = OpsFact(value=row[field],source='AscendTMS',observed_at=now,verified=True,
                source_reference=f'{attempt_id}:board:{number}:column:{FIELDS[field]}:owner-table-schema-001')
            facts[field] = fact
            if field in aliases:
                facts[aliases[field]] = fact
        candidates.append(OpsCandidate(load_number=number,service_date=service_date,identity_verified=True,
            pickup_due=local_date(row['pick_date'],date_format)==service_date,
            delivery_due=local_date(row['drop_date'],date_format)==service_date,facts=facts))
    return candidates


async def select_active_loads_view(executor):
    """Use one observed semantic view control; never a table index or generated selector."""
    controls = []
    for frame in executor.frames():
        for role in ('tab', 'link', 'button'):
            control = frame.get_by_role(role, name=ACTIVE_LOADS, exact=True)
            if await control.count() == 1 and await control.is_visible():
                controls.append(control)
            elif await control.count() > 1:
                raise AscendError('active_loads_view_ambiguous_or_missing')
    if len(controls) != 1:
        raise AscendError('active_loads_view_ambiguous_or_missing')
    control = controls[0]
    safe = await control.evaluate('''e => ({tag:e.tagName, role:e.getAttribute('role'), type:e.getAttribute('type'),
        inForm:!!e.closest('form'), href:e.getAttribute('href')})''')
    if (safe['type'] in {'submit','reset'} or (safe['tag'] == 'BUTTON' and safe['inForm'] and safe['type'] != 'button') or
            (safe['href'] and not safe['href'].startswith('#') and not safe['href'].startswith('/'))):
        raise AscendError('active_loads_view_not_read_only')
    if await control.get_attribute('aria-selected') != 'true':
        await control.click(timeout=5000)
    await executor.guard()


async def login_discover_ops(*, service_date: date, attempt_id: str, board_date_format='ISO', paths=None):
    paths = paths or RuntimePaths.from_environment()
    grant = OpsReadGrant(id=attempt_id, service_date=service_date, board_date_format=board_date_format)
    if attempt_id in {'owner-bootstrap-1752-20260910-02','owner-same-process-1752-01'}:
        raise AscendError('historical_attempt_not_valid_for_ops')
    browser = checked_browser(paths)
    store = Store(paths.path('Data',TENANT,'operations','operations.sqlite3'))
    report = {'attempt_id':attempt_id, 'status':'STOPPED_OPS_DISCOVERY', 'title':'POC #002 — LIVE OPERATIONS',
              'service_date':service_date.isoformat(), 'production_writes':False, 'live_validated':False,
              'stage':'attempt_claim'}
    try:
        with store.transaction():
            if any(r['id'] == attempt_id for r in store.all(TENANT,'ops_read_grant')):
                raise AscendError('ops_grant_consumed_no_retry')
            store.put(TENANT,'ops_read_grant',attempt_id,grant)
        report['stage'] = 'browser_launch_and_owner_confirmation'
        page = await owner_login_page(browser, normal_application_network=True)
        expires = utcnow()+timedelta(minutes=15)
        policies = PolicyEngine(ROOT/'config'/'policies.json')
        def running():
            controls = local_records(paths.path('Data',TENANT,'ascend.sqlite3'), 'ascend_controls')
            return utcnow() < expires and policies.evaluate('read_ascend') == ActionPolicy.ALLOW and not any(
                c.get('paused', True) or c.get('human_takeover', True) for c in controls)
        executor = ReadOnly1752Executor(page, running)
        report['stage'] = 'loads_navigation'
        await executor.navigate_loads()
        report['stage'] = 'active_loads_view_selection'
        await select_active_loads_view(executor)
        report['stage'] = 'data_grid_detection'
        results = []
        display_date = service_date.strftime('%m/%d/%Y') if board_date_format == 'US' else service_date.isoformat()
        arguments = {'headers':HEADERS,'fields':FIELDS,'display_date':display_date,'format':board_date_format}
        for _ in range(20):
            await asyncio.sleep(0.5)
            await executor.guard()
            results = [await frame.evaluate(BOARD, arguments) for frame in executor.frames()]
            if any(r['overflow'] or r['grids'] for r in results):
                break
        grid = select_grid(results)
        report.update(valid_data_grid_found=True, observed_row_count=grid['visible_rows'])
        # A second DOM read must agree; no reload, detail opening or pagination action.
        await executor.guard()
        reread = select_grid([await frame.evaluate(BOARD, arguments) for frame in executor.frames()])
        if grid != reread:
            raise AscendError('ops_board_changed_during_read')
        report['stage'] = 'row_extraction'
        candidates = board_candidates(grid, service_date, board_date_format, attempt_id)
        report.update(pickup_count=sum(c.pickup_due for c in candidates),
                      delivery_count=sum(c.delivery_due for c in candidates))
        unknown = grid['unknown_dates']
        board_coverage = coverage(grid)
        evidence = board_evidence(grid, source_view=ACTIVE_LOADS, service_date=service_date, attempt_id=attempt_id)
        if not (await observe_session(page, IdentityConfig(origin=ORIGIN))).session_authenticated or not running():
            raise AscendError('ops_authority_or_session_lost')
        with store.transaction():
            for candidate in candidates:
                store.put(TENANT,'ops_candidate',attempt_id+':'+candidate.load_number, candidate)
        report['stage'] = 'pickup_delivery_reconciliation'
        manifest = build_manifest(attempt_id, service_date, candidates, {}, coverage=board_coverage,
                                  source_view=ACTIVE_LOADS, board_row_count=grid['visible_rows'],
                                  evidence_hash=evidence['evidence_hash'])
        manifest['board_evidence'] = evidence | {'contract_source':'owner-table-schema-001',
            'pagination':grid['pagination']}
        manifest['unparsed_date_row_count'] = unknown
        manifest['owner_attested_board_date_format'] = board_date_format
        report['stage'] = 'local_manifest_persistence'
        store.put(TENANT,'ops_manifest',attempt_id,manifest)
        target = paths.path('Data',TENANT,'operations',attempt_id+'-manifest.json')
        target.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        paths.path('Data',TENANT,'operations',attempt_id+'-owner-report.md').write_text(owner_report(manifest), encoding='utf-8')
        report.update(status=manifest['reconciliation_status'], manifest_id=attempt_id,
            pickup_count=len(manifest['PICKUP_TRACKING_QUEUE']), delivery_count=len(manifest['DELIVERY_WATCH_QUEUE']),
            expected_pickups=8, expected_deliveries=3, unknown_date_rows=unknown,
            coverage=board_coverage, scope_complete=board_coverage == 'COMPLETE_CURRENT_BOARD',
            system_coverage_complete=False, pickup_count_difference=len(manifest['PICKUP_TRACKING_QUEUE'])-8,
            delivery_count_difference=len(manifest['DELIVERY_WATCH_QUEUE'])-3,
            pickup_load_ids=[row['load_number'] for row in manifest['PICKUP_TRACKING_QUEUE']],
            delivery_load_ids=[row['load_number'] for row in manifest['DELIVERY_WATCH_QUEUE']])
    except AscendError as error:
        allowed = {'ops_board_changed_during_read','ops_board_bound_exceeded','ops_board_headers_missing_or_ambiguous',
            'board_load_identity_unrecognized','board_duplicate_identity_conflict','ops_candidate_bound_exceeded',
            'ops_detail_changed_or_exceeded_bound','ops_detail_load_mismatch','ops_list_detail_date_conflict',
            'ops_authority_or_session_lost','ops_grant_consumed_no_retry', 'detail_load_identity_unverified',
            'exact_load_discovery_ambiguous_or_missing','exact_load_read_control_unknown',
            'active_loads_view_ambiguous_or_missing','active_loads_view_not_read_only','ops_unknown_board_source'}
        report['error_code'] = str(error) if str(error) in allowed else 'bounded_read_gate_failed'
        report['reason'] = 'A bounded read gate rejected the operation; see error_code and stage.'
    except Exception as error:
        report.update(sanitized_failure(error))
    finally:
        try:
            await browser.close()
        finally:
            store.close()
            save_report(paths,'ops-discovery-result',report)
    return report


def sanitized_failure(error):
    """Classify locally without printing exception messages, arguments or traceback."""
    if isinstance(error, AttributeError):
        return {'error_code':'ops_internal_attribute_error',
                'reason':'An internal attribute lookup failed at the recorded stage.'}
    if isinstance(error, TimeoutError) or type(error).__name__ == 'TimeoutError':
        return {'error_code':'ops_read_timeout','reason':'The bounded operation timed out at the recorded stage.'}
    return {'error_code':'ops_unexpected_execution_error',
            'reason':'An unexpected local execution failure occurred at the recorded stage.'}
