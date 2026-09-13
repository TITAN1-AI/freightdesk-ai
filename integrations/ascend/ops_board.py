"""Structural board parsing; Active Loads is the operational source, All Loads is audit-only."""
from datetime import date
from pathlib import Path

from integrations.ascend.models import AscendError
from app.services.action_ledger import payload_hash

HEADERS = ['Load ID','Load Status','Last Contact/Tracking','Customer','Picks','Pick Date','Drops',
           'Drop Date','Users & Roles','Carrier','Driver','Equipment','Power Unit','Trailer','Distance',
           'Weight','Income','Expenses','Gross Profit/Loss',None,'Reference','Truck Status','Branch',None,
           'Smart Capacity','TruckSmarter','Asset Group','Container','Last Free Day','Created',
           'Load Posting Notes','Public Load Notes','Temperature']
FIELDS = {'load_id':0,'load_status':1,'last_contact_tracking':2,'customer':3,'pick_date':5,
          'drop_date':7,'carrier':9,'driver':10,'equipment':11,'power_unit':12,'trailer':13,'truck_status':21}
SCAN = Path(__file__).with_name('ops_board.js').read_text(encoding='utf-8')
ACTIVE_LOADS = 'Active Loads'
ALL_LOADS = 'All Loads'


def select_grid(results):
    if any(r['overflow'] for r in results):
        raise AscendError('ops_board_bound_exceeded')
    grids = [g for r in results for g in r['grids']]
    if len(grids) != 1:
        raise AscendError('ops_board_headers_missing_or_ambiguous')
    return grids[0]


def coverage(grid):
    """Only explicit DOM pagination totals certify this current filtered board."""
    p = grid['pagination']
    complete = (p['next_disabled'] is True and p['previous_disabled'] is True and
                p['start'] == 1 and p['end'] == p['total'] == grid['visible_rows'] and
                p['page_size'] is not None and p['total'] <= p['page_size'])
    return 'COMPLETE_CURRENT_BOARD' if complete else 'VISIBLE_BOARD_ONLY'


def board_evidence(grid, *, source_view: str, service_date: date, attempt_id: str):
    """Immutable, non-content evidence metadata for one structural board observation."""
    if source_view not in {ACTIVE_LOADS, ALL_LOADS}:
        raise AscendError('ops_unknown_board_source')
    payload = {'attempt_id': attempt_id, 'source_view': source_view,
               'service_date': service_date.isoformat(), 'rows': grid['rows'],
               'visible_rows': grid['visible_rows'], 'pagination': grid['pagination']}
    return {'source_view': source_view, 'service_date': service_date.isoformat(),
            'board_row_count': grid['visible_rows'], 'coverage': coverage(grid),
            'evidence_hash': payload_hash(payload), 'contract': 'AscendBoardStructuralContract v1'}


def all_loads_cross_check(active_candidates, all_candidates):
    """Never expands Active Loads' operational population from the audit view."""
    active = {candidate.load_number for candidate in active_candidates}
    all_ids = {candidate.load_number for candidate in all_candidates}
    missing = sorted(active - all_ids, key=int)
    extra = sorted(all_ids - active, key=int)
    return {'active_loads_missing_from_all_loads': missing,
            'NON_ACTIVE_SERVICE_DATE_RECORDS': extra}
