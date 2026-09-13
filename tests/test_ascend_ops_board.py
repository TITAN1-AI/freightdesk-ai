import asyncio
import html
import json
import os
from datetime import date

import pytest

from app.services.live_ops import build_manifest
from integrations.ascend import ops_board as module
from integrations.ascend.models import AscendError
from integrations.ascend.ops_discovery import board_candidates


def table(rows, headers=None):
    headers = module.HEADERS if headers is None else headers
    head = ''.join('<th>'+html.escape(h or '')+'</th>' for h in headers)
    body = ''
    for number, pick, drop in rows:
        cells = ['PRIVATE']*33
        for name, i in module.FIELDS.items():
            cells[i] = 'Synthetic '+name
        cells[0],cells[1],cells[5],cells[7] = number,'Completed',pick,drop
        cells[16],cells[30],cells[31] = 'FINANCIAL_SECRET','PRIVATE_NOTE','PUBLIC_NOTE'
        body += '<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in cells)+'</tr>'
    return '<table role="grid"><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table>'


def test_observed_grid_contract_offline(tmp_path):
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as runtime:
            context=await runtime.chromium.launch_persistent_context(str(tmp_path/'profile'),channel='msedge',
                headless=True,env={**os.environ,'TEMP':str(tmp_path),'TMP':str(tmp_path)})
            await context.route('**/*',lambda r:r.abort())
            try:
                page=await context.new_page()
                rows=[('90001','09/11/2026','09/12/2026'),('90002','09/10/2026','09/11/2026'),
                      ('90003','09/11/2026','09/11/2026'),('90004','09/10/2026','09/12/2026')]
                args={'headers':module.HEADERS,'fields':module.FIELDS,'display_date':'09/11/2026','format':'US'}
                wrapper='<div class="dataTables_wrapper">'+table([])+table(rows)+'''
                    <div class="dataTables_length"><select><option>100</option></select></div>
                    <div class="dataTables_info">Showing 1 to 4 of 4 entries</div>
                    <div class="dataTables_paginate"><button class="previous disabled">Previous</button>
                    <button class="next disabled">Next</button></div></div>'''
                await page.set_content(wrapper)
                result=await page.evaluate(module.SCAN,args)
                grid=module.select_grid([result])
                assert grid['visible_rows']==4 and len(grid['rows'])==3
                assert [r['load_id'] for r in grid['rows']]==['90001','90002','90003']
                assert set(grid['rows'][0])==set(module.FIELDS)
                assert 'SECRET' not in json.dumps(result) and 'NOTE' not in json.dumps(result)
                assert module.coverage(grid)=='COMPLETE_CURRENT_BOARD'
                candidates=board_candidates(grid,date(2026,9,11),'US','synthetic-board')
                assert candidates[0].facts['load_id'].value=='90001'
                assert candidates[0].facts['driver'].value=='Synthetic driver'
                assert candidates[0].stops==[] and 'driver_phone' not in candidates[0].facts
                manifest=build_manifest('synthetic',date(2026,9,11),candidates,{})
                assert [r['load_number'] for r in manifest['PICKUP_TRACKING_QUEUE']]==['90001','90003']
                assert [r['load_number'] for r in manifest['DELIVERY_WATCH_QUEUE']]==['90002','90003']
                assert manifest['pickup_count_difference']==-6 and manifest['delivery_count_difference']==-1
                assert 'Synthetic driver' not in json.dumps(manifest)
                await page.set_content(wrapper.replace('class="next disabled"','class="next"'))
                assert module.coverage(module.select_grid([await page.evaluate(module.SCAN,args)]))=='VISIBLE_BOARD_ONLY'
                await page.set_content(table(rows))
                assert module.coverage(module.select_grid([await page.evaluate(module.SCAN,args)]))=='VISIBLE_BOARD_ONLY'
                for changed in (module.HEADERS[:5]+['Pickup Date']+module.HEADERS[6:],module.HEADERS[:-1]):
                    await page.set_content(table(rows,changed))
                    with pytest.raises(AscendError,match='ambiguous'):
                        module.select_grid([await page.evaluate(module.SCAN,args)])
                await page.set_content(table(rows)+table(rows))
                with pytest.raises(AscendError,match='ambiguous'):
                    module.select_grid([await page.evaluate(module.SCAN,args)])
                await page.set_content(table([('not-a-load','09/11/2026','09/12/2026')]))
                with pytest.raises(AscendError,match='identity_unrecognized'):
                    board_candidates(module.select_grid([await page.evaluate(module.SCAN,args)]),date(2026,9,11),'US','test')
            finally:
                await context.close()
    asyncio.run(run())


@pytest.mark.parametrize('change',[{'total':49},{'start':2},{'page_size':None},{'next_disabled':None}])
def test_coverage_requires_explicit_current_board_evidence(change):
    p={'total':48,'start':1,'end':48,'page_size':100,'next_disabled':True,'previous_disabled':True}
    assert module.coverage({'visible_rows':48,'pagination':p|change})=='VISIBLE_BOARD_ONLY'
