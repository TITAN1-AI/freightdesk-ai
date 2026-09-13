"""DOM-only bounded presentation normalization. No provider mutations or DataTables internals."""
import asyncio
import time
import re

from app.services.action_ledger import payload_hash
from app.services.live_ops_carrierview import PICKUPS, DELIVERIES
from integrations.ascend.models import AscendError
from integrations.ascend.ops_board import HEADERS, FIELDS, SCAN

TABLES='table,[role="grid"],[role="table"]'
SEARCH='.dataTables_filter input[type="search"],.dt-search input[type="search"]'
SIZE='.dataTables_length select,.dt-length select'
FIRST='.dataTables_paginate .first,.dt-paging .first'
ONE='.dataTables_paginate a,.dataTables_paginate button,.dt-paging a,.dt-paging button'
META=r'''t => {
    const w=t.closest('.dataTables_wrapper,.dt-container');
    if(!w) return {wrapper_found:false};
    const visible=e=>!!e.getClientRects().length && getComputedStyle(e).visibility!=='hidden';
    const ss=[...w.querySelectorAll('.dataTables_filter input[type="search"],.dt-search input[type="search"]')].filter(visible);
    const lengths=[...w.querySelectorAll('.dataTables_length select,.dt-length select')].filter(visible);
    const filters=[];
    for(const e of w.querySelectorAll('input,select')) {
        if(!visible(e) || ss.includes(e) || lengths.includes(e)) continue;
        const label=(e.getAttribute('aria-label') || e.labels?.[0]?.textContent || '').replace(/\s+/g,' ').trim().toLowerCase();
        const kind=['status','date','pickup date','delivery date','branch','user','users','filter'].includes(label)?label:
            e.closest('thead')?'column_filter':null;
        if(!kind) continue;
        const selected=e.tagName==='SELECT'?(e.selectedOptions[0]?.textContent||'').trim().toLowerCase():null;
        filters.push({kind,control_type:e.tagName.toLowerCase(),value_present:!!e.value,
            selected_state:selected!==null && ['all','any','active','completed','future','all statuses','all branches','all users'].includes(selected)?selected:'UNKNOWN',
            neutral:!e.value || (selected!==null && ['all','any','all statuses','all branches','all users'].includes(selected))});
    }
    return {wrapper_found:true,search_count:ss.length,search_nonempty:ss.some(e=>!!e.value.trim()),
        size_control_count:lengths.length,page_size:lengths.length===1 && /^\d+$/.test(lengths[0].value)?Number(lengths[0].value):null,
        size_100_available:lengths.length===1 && [...lengths[0].options].some(o=>o.value==='100'),
        processing:[...w.querySelectorAll('.dataTables_processing,.dt-processing,[aria-busy="true"]')].some(visible),
        other_filters:filters};
}'''


def scope_metadata(grid):
    from datetime import date
    from integrations.ascend.ops_discovery import local_date
    rows=grid['rows']
    pickups=[r['load_id'] for r in rows if local_date(r.get('pick_date'),'US')==date(2026,9,11)]
    deliveries=[r['load_id'] for r in rows if local_date(r.get('drop_date'),'US')==date(2026,9,11)]
    ids=[r['load_id'] for r in rows]
    safe=all(isinstance(n,str) and n.isdigit() and 1<=len(n)<=20 for n in ids)
    if not safe:
        raise AscendError('board_load_identity_unrecognized')
    approved=PICKUPS|DELIVERIES
    matches=(len(ids)==len(set(ids))==11 and set(ids)==approved and len(pickups)==8 and
             len(deliveries)==3 and set(pickups)==PICKUPS and set(deliveries)==DELIVERIES)
    return {'observed_row_count':grid['visible_rows'],'observed_approved_load_ids':sorted(set(ids)&approved,key=int),
        'missing_approved_load_ids':sorted(approved-set(ids),key=int),'unexpected_load_ids':sorted(set(ids)-approved,key=int),
        'pickup_count':len(pickups),'delivery_count':len(deliveries),'exact_scope_reconciled':matches}


def semantic_hash(grid):
    # Only selected operational row fields, order independent. Never hash page/search/DOM locator state.
    return payload_hash({'source_view':'ACTIVE_LOADS','service_date':'2026-09-11',
        'rows':sorted([{k:r.get(k) for k in FIELDS} for r in grid['rows']],key=lambda r:r['load_id'])})


async def _selected(executor):
    found=[]
    for frame in executor.frames():
        for role in ('tab','link','button'):
            items=frame.get_by_role(role,name='Active Loads',exact=True)
            for i in range(await items.count()):
                item=items.nth(i)
                if await item.is_visible():
                    found.append(await item.evaluate('''e => e.getAttribute('aria-selected')==='true' ||
                        ['page','true'].includes(e.getAttribute('aria-current')) || e.classList.contains('active') ||
                        (e.parentElement?.tagName==='LI' && e.parentElement.classList.contains('active'))'''))
    return len(found)==1 and found[0]


async def _snapshot(executor):
    await executor.guard()
    if not await _selected(executor):
        return None
    found=[]
    for frame in executor.frames():
        result=await asyncio.wait_for(frame.evaluate(SCAN,{'headers':HEADERS,'fields':FIELDS,'display_date':'09/11/2026','format':'US'}),timeout=3)
        if result['overflow']:
            raise AscendError('ops_board_bound_exceeded')
        for grid in result['grids']:
            t=frame.locator(TABLES).nth(grid['table_index'])
            meta=await t.evaluate(META)
            found.append((grid,meta,t))
    if len(found)>1:
        raise AscendError('ops_board_headers_missing_or_ambiguous')
    return found[0] if found else None


async def _settle(executor,timeout,interval,stable_seconds,prefer_scope=False):
    deadline=time.monotonic()+timeout
    last=None
    stable_since=time.monotonic()
    current=None
    while True:
        current=await _snapshot(executor)
        now=time.monotonic()
        signature=payload_hash(current[:2]) if current else None
        if signature!=last:
            last=signature
            stable_since=now
        stable=current and not current[1].get('processing') and now-stable_since>=stable_seconds
        if stable and (not prefer_scope or scope_metadata(current[0])['exact_scope_reconciled']):
            return current
        if now>=deadline:
            if stable:
                return current
            raise AscendError('board_render_not_settled')
        await asyncio.sleep(interval)


async def normalize_board(executor,observe,*,timeout=15,interval=0.25,stable_seconds=1):
    actions=[]
    async def snapshot(prefer_scope=False):
        result=await _settle(executor,timeout,interval,stable_seconds,prefer_scope)
        grid,meta,_=result
        observe({'source_view':'ACTIVE_LOADS','ui_filters':meta,'pagination':grid['pagination'],
                 'normalization_actions':list(actions),'semantic_board_hash':semantic_hash(grid),
                 'pagination_page':((grid['pagination']['start']-1)//meta['page_size']+1) if meta.get('page_size') and grid['pagination']['start'] else None,
                 **scope_metadata(grid)})
        return result
    grid,meta,t=await snapshot()
    if not meta.get('wrapper_found'):
        raise AscendError('board_presentation_wrapper_unknown')
    def wrapper(table):
        return table.locator('xpath=ancestor::*[contains(concat(" ",normalize-space(@class)," ")," dataTables_wrapper ") or contains(concat(" ",normalize-space(@class)," ")," dt-container ")][1]')
    async def safe(control):
        await executor.guard()
        if await control.count()!=1 or not await control.is_visible():
            raise AscendError('board_presentation_control_ambiguous')
        if not await control.evaluate('''e => !['submit','reset','file','password'].includes(e.getAttribute('type')) &&
            !(e.tagName==='BUTTON' && e.closest('form') && e.getAttribute('type')!=='button') &&
            !(e.tagName==='A' && e.getAttribute('href') && !e.getAttribute('href').startsWith('#'))'''):
            raise AscendError('board_presentation_control_not_safe')
    if meta['search_count']>1 or meta['size_control_count']>1:
        raise AscendError('board_presentation_control_ambiguous')
    if meta['search_nonempty']:
        control=wrapper(t).locator(SEARCH)
        await safe(control)
        await control.fill('')
        actions.append('CLEAR_TABLE_SEARCH')
        grid,meta,t=await snapshot()
    if meta['page_size'] is not None and meta['page_size']<100:
        if not meta['size_100_available']:
            raise AscendError('board_page_size_option_unverified')
        control=wrapper(t).locator(SIZE)
        await safe(control)
        await control.select_option('100')
        actions.append('SET_PAGE_SIZE_100')
        grid,meta,t=await snapshot()
    if grid['pagination']['start'] is not None and grid['pagination']['start']>1:
        control=wrapper(t).locator(FIRST)
        if await control.count()!=1:
            control=wrapper(t).locator(ONE).filter(has_text=re.compile(r'^1$'))
        await safe(control)
        await control.click(timeout=5000)
        actions.append('FIRST_PAGE')
        grid,meta,t=await snapshot()
    if meta['search_nonempty'] or any(not f['neutral'] for f in meta['other_filters']):
        raise AscendError('board_filter_requires_observed_reset_contract')
    grid,meta,t=await snapshot(prefer_scope=True)
    if not scope_metadata(grid)['exact_scope_reconciled']:
        raise AscendError('normalized_board_scope_mismatch')
    return grid
