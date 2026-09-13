"""Owner-executed All Loads schema observation; no detail reads or manifest building."""
import asyncio
import re
import time
from datetime import timedelta
from pathlib import Path

from app.core.config import ROOT
from app.core.runtime import RuntimePaths
from app.models.domain import ActionPolicy, utcnow
from app.policies.engine import PolicyEngine
from app.services.ascend_live import local_records
from app.services.store import Store
from integrations.ascend.field_discovery import ReadOnly1752Executor
from integrations.ascend.models import AscendError
from integrations.ascend.session_continuity import checked_browser, owner_login_page, save_report

SCAN_TABLES = Path(__file__).with_name('table_structure.js').read_text(encoding='utf-8')
FIELDS = {'load_number': {'load #', 'load number', 'load no.'}, 'pickup_date': {'pickup date'},
          'delivery_date': {'delivery date'}, 'status': {'status'}}


def contract(tables, attempt_id):
    """Exact semantic labels only; conflicting, spanning or unaligned columns stay unknown."""
    for table in tables:
        mappings = {}
        for field, labels in FIELDS.items():
            found = [h for h in table['headers'] if h['label'] and
                     ' '.join(h['label'].split()).lower() in labels]
            indexes = {h['column_index'] for h in found}
            valid = len(indexes) == 1 and not any(h['span_ambiguous'] for h in table['headers'])
            if valid:
                index = next(iter(indexes))
                competing = {f for f, names in FIELDS.items() for h in table['headers']
                             if h['column_index'] == index and h['label'] and
                             ' '.join(h['label'].split()).lower() in names}
                local = [h for h in table['headers'] if h['column_index'] == index]
                valid = competing == {field} and index < table['first_data_row_cell_count'] and all(
                    (not h['label'] or ' '.join(h['label'].split()).lower() in labels) and
                    h['aria_colindex'] in {None,index+1} for h in local) and table.get('uniform_cell_count',False)
            mappings[field] = {'state':'OBSERVED_PROPOSAL' if valid else 'UNKNOWN',
                               'column_index':next(iter(indexes)) if valid else None,
                               'confidence':'exact_label_local_index_only' if valid else 'insufficient_or_conflicting',
                               'evidence':found}
        table['mappings'] = mappings
    return {'contract_type':'AscendAllLoadsTableContract','version':1,'provider':'AscendTMS',
            'source':'live browser DOM','observed_at':utcnow().isoformat(),'attempt_id':attempt_id,
            'tenant_identity':'Booking Logistics','tenant_identity_source':'OWNER_ATTESTED',
            'service_date':'2026-09-11','display_date':'09/11/2026','column_index_base':0,
            'coverage':'CURRENT_LOADED_DOM_ONLY','tables':tables,'table_count':len(tables),
            'matching_dom_rows':sum(len(t['date_matches']) for t in tables),
            'date_occurrence_count':sum(c['occurrence_count'] for t in tables for r in t['date_matches'] for c in r['columns']),
            'counts_may_include_cloned_rows':True,
            'parser_rerun_authorized':False,'live_validated':False}


async def poll_tables(executor, *, timeout=15):
    start = time.monotonic()
    last = []
    while True:
        await executor.guard()
        last = []
        for frame_index, frame in enumerate(executor.frames()):
            result = await asyncio.wait_for(frame.evaluate(SCAN_TABLES, {}), timeout=3)
            if result['overflow']:
                raise AscendError('table_structure_bound_exceeded')
            last.extend(dict(t, frame_index=frame_index) for t in result['tables'])
        if len(last) > 30:
            raise AscendError('table_structure_bound_exceeded')
        elapsed = time.monotonic()-start
        # Allow initialization even when the initial skeleton contains placeholder cells.
        if elapsed >= 1 and any(t['visible_row_count'] and (t['header_cell_count'] or t.get('headers')) for t in last):
            return last, elapsed, True
        if elapsed >= timeout:
            return last, elapsed, False
        await asyncio.sleep(0.25)


async def diagnose_table(*, attempt_id, paths=None):
    if not re.fullmatch(r'owner-table-schema-[0-9]{3}', attempt_id):
        raise AscendError('table_diagnostic_attempt_id_required')
    paths = paths or RuntimePaths.from_environment()
    browser = checked_browser(paths)
    store = Store(paths.path('Data','booking-logistics','operations','operations.sqlite3'))
    report = {'attempt_id':attempt_id,'status':'STOPPED_TABLE_DIAGNOSTIC','production_writes':False}
    try:
        with store.transaction():
            if any(r['id'] == attempt_id for r in store.all('booking-logistics','table_diagnostic_grant')):
                raise AscendError('table_diagnostic_attempt_consumed')
            store.put('booking-logistics','table_diagnostic_grant',attempt_id,
                      {'id':attempt_id,'consumed':True,'service_date':'2026-09-11'})
        page = await owner_login_page(browser, normal_application_network=True)
        expires = utcnow()+timedelta(minutes=15)
        policy = PolicyEngine(ROOT/'config'/'policies.json')

        def running():
            controls = local_records(paths.path('Data','booking-logistics','ascend.sqlite3'),'ascend_controls')
            return utcnow() < expires and policy.evaluate('read_ascend') == ActionPolicy.ALLOW and not any(
                c.get('paused',True) or c.get('human_takeover',True) for c in controls)

        executor = ReadOnly1752Executor(page, running)
        await executor.navigate_loads()  # No search, click, pagination or detail method is called.
        tables, elapsed, rendered = await poll_tables(executor)
        await executor.guard()
        report.update(contract(tables, attempt_id))
        report.update(status='TABLE_STRUCTURE_OBSERVED' if rendered else 'TABLE_STRUCTURE_INCOMPLETE',
                      render_wait_elapsed=round(elapsed,3),data_rendered=rendered)
    except AscendError as exc:
        code = str(exc)
        report['error_code'] = code if code in {'table_structure_bound_exceeded','table_diagnostic_attempt_consumed',
            'discovery_policy_pause_or_expiry','discovery_session_not_authenticated','owner_login_page_ambiguous'} else 'table_diagnostic_gate_failed'
    except Exception:
        report['error_code'] = 'table_diagnostic_execution_failed'
    finally:
        try:
            await browser.close()
        finally:
            store.close()
            save_report(paths,'all-loads-table-contract',report)
    return report
