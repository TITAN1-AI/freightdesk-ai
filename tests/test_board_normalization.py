import asyncio
import html
import json
import os
from types import SimpleNamespace

import pytest

from app.services.live_ops_carrierview import PICKUPS, DELIVERIES
from integrations.ascend import board_normalization as module
from integrations.ascend.ops_board import HEADERS, FIELDS
from integrations.ascend.models import AscendError


def grid():
    return {'visible_rows':12,'rows':[dict.fromkeys(FIELDS,'') | {'load_id':n,
        'pick_date':'09/11/2026' if n in PICKUPS else '09/10/2026',
        'drop_date':'09/11/2026' if n in DELIVERIES else '09/12/2026'} for n in sorted(PICKUPS|DELIVERIES,key=int)]}


def test_semantic_hash_and_scope():
    g=grid()
    assert module.scope_metadata(g)['exact_scope_reconciled']
    assert module.semantic_hash(g)==module.semantic_hash(g|{'visible_rows':100,'table_index':9,'pagination':{'start':3},'rows':g['rows'][::-1]})
    changed=g | {'rows':[dict(r,load_status='Changed') for r in g['rows']]}
    assert module.semantic_hash(g)!=module.semantic_hash(changed)
    wrong=g | {'rows':[dict(r,load_id='1999') if r['load_id']=='1755' else r for r in g['rows']]}
    info=module.scope_metadata(wrong)
    assert info['pickup_count']==8 and not info['exact_scope_reconciled']
    assert info['missing_approved_load_ids']==['1755'] and info['unexpected_load_ids']==['1999']
    extra=g | {'rows':g['rows']+[dict(g['rows'][0],load_id='1999')]}
    assert not module.scope_metadata(extra)['exact_scope_reconciled']


@pytest.mark.parametrize('scenario',['search','page_size','pagination','unsupported_filter','wrong_ids'])
def test_presentation_normalization_offline_browser(tmp_path,scenario):
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as runtime:
            context=await runtime.chromium.launch_persistent_context(str(tmp_path/'profile'),channel='msedge',
                headless=True,env={**os.environ,'TEMP':str(tmp_path),'TMP':str(tmp_path)})
            await context.route('**/*',lambda r:r.abort())
            try:
                page=await context.new_page()
                hs='<thead><tr>'+''.join('<th>'+html.escape(h or '')+'</th>' for h in HEADERS)+'</tr></thead>'
                rows=grid()['rows']
                if scenario=='wrong_ids':
                    rows[0]['load_id']='1999'
                rawrows=[]
                for row in rows:
                    cells=['PRIVATE_VALUE']*33
                    for field,col in FIELDS.items():
                        cells[col]=row[field]
                    rawrows.append('<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in cells)+'</tr>')
                doc='''<button role="tab" aria-selected="true" type="button">Active Loads</button>
                <div class="dataTables_wrapper"><div class="dataTables_filter"><input type="search"></div>
                <div class="dataTables_length"><select><option>5</option><option selected>100</option></select></div>'''
                if scenario=='unsupported_filter':
                    doc+='<select aria-label="Branch"><option>PRIVATE_BRANCH</option></select>'
                doc+='<table role="grid">'+hs+'</table><table role="grid" id="data">'+hs+'<tbody></tbody></table>'
                doc+='''<div class="dataTables_info"></div><div class="dataTables_paginate">
                <button type="button" class="first">First</button><button type="button" class="previous">Previous</button>
                <button type="button" class="next">Next</button></div>
                <form onsubmit="window.mutations++;return false"><button type="submit">Save</button></form></div>'''
                doc+='<script>window.mutations=0;const rows='+json.dumps(rawrows)+';'+'''
                let pageNumber=1;
                const search=document.querySelector('input[type=search]'),size=document.querySelector('.dataTables_length select');
                function render(){const selected=search.value?rows.slice(0,1):rows.slice(0,Number(size.value));
                  document.querySelector('#data tbody').innerHTML=selected.join('');
                  const start=pageNumber===1?1:6;
                  document.querySelector('.dataTables_info').textContent=`Showing ${start} to ${start+selected.length-1} of ${selected.length} entries`;
                }
                search.addEventListener('input',()=>setTimeout(render,40));
                size.addEventListener('change',()=>{pageNumber=1;render()});
                document.querySelector('.first').onclick=()=>{pageNumber=1;render()};
                '''
                if scenario=='search':
                    doc+='search.value="PRIVATE_RETAINED_SEARCH";'
                if scenario=='page_size':
                    doc+='size.value="5";'
                if scenario=='pagination':
                    doc+='pageNumber=2;'
                doc+='render();</script>'
                await page.set_content(doc)
                async def guard():
                    pass
                executor=SimpleNamespace(guard=guard,frames=lambda:[page.main_frame])
                observations=[]
                async def normalize():
                    return await module.normalize_board(executor,observations.append,timeout=.35,interval=.01,stable_seconds=.06)
                if scenario in {'unsupported_filter','wrong_ids'}:
                    with pytest.raises(AscendError,match='filter_requires|scope_mismatch'):
                        await normalize()
                else:
                    result=await normalize()
                    assert module.scope_metadata(result)['exact_scope_reconciled']
                    expected={'search':'CLEAR_TABLE_SEARCH','page_size':'SET_PAGE_SIZE_100','pagination':'FIRST_PAGE'}[scenario]
                    assert expected in observations[-1]['normalization_actions']
                    assert result['table_index']==1  # Clone rejected structurally; index is observed, not configured.
                assert await page.evaluate('window.mutations')==0
                assert 'PRIVATE' not in json.dumps(observations)
                if scenario=='search':
                    assert observations[0]['observed_row_count']==1 and observations[0]['ui_filters']['search_nonempty']
                    assert not observations[-1]['ui_filters']['search_nonempty']
            finally:
                await context.close()
    asyncio.run(run())
