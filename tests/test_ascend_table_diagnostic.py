import asyncio
import json
import os
from types import SimpleNamespace

from integrations.ascend import table_diagnostic as module


def test_table_structure_offline_browser(tmp_path):
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as runtime:
            context = await runtime.chromium.launch_persistent_context(str(tmp_path/'profile'),channel='msedge',
                headless=True,env={**os.environ,'TEMP':str(tmp_path),'TMP':str(tmp_path)})
            await context.route('**/*',lambda route:route.abort())
            try:
                page=await context.new_page()
                await page.set_content('''<div class="dataTables_wrapper"><div class="dataTables_length"><select><option>25</option></select></div>
                <div style="width:100px;overflow:auto"><table style="width:900px"><thead><tr>
                <th>Load #</th><th> Pickup Date </th><th>Delivery Date</th><th>Status</th><th>Customer</th>
                </tr></thead><tbody><tr><td>1761</td><td>09/11/2026</td><td>09/11/2026</td>
                <td>PRIVATE_STATUS</td><td aria-label="PRIVATE_CUSTOMER" style="display:none">PRIVATE_CUSTOMER +15555555555</td></tr></tbody></table></div>
                <div class="dataTables_paginate"><button>Next</button></div></div>''')
                result=await page.evaluate(module.SCAN_TABLES,{})
                assert not result['overflow']
                t=result['tables'][0]
                assert t['page_size']==25 and t['pagination_present'] and t['hidden_columns'] and t['horizontal_scrolling']
                assert t['date_matches'][0]['load_number']=='1761'
                assert t['date_matches'][0]['multiple_date_columns']
                assert len(t['date_matches'][0]['columns'])==2
                assert 'PRIVATE' not in json.dumps(result) and '15555555555' not in json.dumps(result)
                c=module.contract(result['tables'],'synthetic')
                assert c['tables'][0]['mappings']['pickup_date']['column_index']==1
                assert c['tables'][0]['mappings']['status']['state']=='OBSERVED_PROPOSAL'
                await page.set_content('''<div role="grid"><div role="row"><span role="columnheader" aria-colindex="1" aria-label="Load #"></span>
                <span role="columnheader" aria-colindex="8">Pickup Date</span></div><div role="row">
                <span role="gridcell">1762</span><span role="gridcell">09/11/2026</span></div></div>''')
                c=module.contract((await page.evaluate(module.SCAN_TABLES,{}))['tables'],'synthetic')
                assert c['tables'][0]['mappings']['pickup_date']['state']=='UNKNOWN'
                await page.set_content('''<table><thead><tr><th colspan="2">Load #</th><th>Pickup Date</th></tr></thead>
                <tbody><tr><td>1765</td><td>999999</td><td>09/11/2026</td></tr></tbody></table>''')
                c=module.contract((await page.evaluate(module.SCAN_TABLES,{}))['tables'],'synthetic')
                assert c['tables'][0]['mappings']['load_number']['state']=='UNKNOWN'
                assert c['tables'][0]['date_matches'][0]['load_number'] is None
                await page.set_content('''<table><tbody><tr><td data-title="Load #">1763</td>
                <td data-title="Delivery Date">09/11/2026</td><td title="PRIVATE_PHONE">PRIVATE_NOTE</td></tr></tbody></table>''')
                c=module.contract((await page.evaluate(module.SCAN_TABLES,{}))['tables'],'synthetic')
                assert c['tables'][0]['mappings']['delivery_date']['column_index']==1
                assert 'PRIVATE' not in json.dumps(c)
                await page.set_content('''<table><thead><tr><th>Load #</th><th>Pickup</th></tr><tr><th>Load #</th><th>Pickup</th></tr></thead>
                <tbody><tr><td>1764</td><td>09/11/2026</td></tr></tbody></table>''')
                c=module.contract((await page.evaluate(module.SCAN_TABLES,{}))['tables'],'synthetic')
                assert c['tables'][0]['duplicated_headers']
                assert c['tables'][0]['mappings']['pickup_date']['state']=='UNKNOWN'
                await page.set_content('<iframe srcdoc="&lt;table&gt;&lt;tr&gt;&lt;td&gt;09/11/2026&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;"></iframe>')
                assert len(page.frames)==2
                assert (await page.frames[1].evaluate(module.SCAN_TABLES,{}))['tables'][0]['date_matches']
            finally:
                await context.close()
    asyncio.run(run())


def test_diagnostic_grant_and_same_process_boundary(tmp_path,monkeypatch):
    events=[]
    page=object()
    class Paths:
        def path(self,*parts):
            return tmp_path.joinpath(*parts)
    class Browser:
        async def close(self):
            events.append('close')
    async def login(browser,*,normal_application_network):
        assert normal_application_network is True
        events.append('owner_confirmed')
        return page
    class Executor:
        def __init__(self,p,running):
            assert p is page and running()
        async def navigate_loads(self):
            events.append('loads')
        async def guard(self):
            pass
    async def poll(executor):
        return [],15,False
    monkeypatch.setattr(module,'checked_browser',lambda paths:Browser())
    monkeypatch.setattr(module,'owner_login_page',login)
    monkeypatch.setattr(module,'ReadOnly1752Executor',Executor)
    monkeypatch.setattr(module,'poll_tables',poll)
    monkeypatch.setattr(module,'local_records',lambda *args:[])
    monkeypatch.setattr(module,'PolicyEngine',lambda *args:SimpleNamespace(evaluate=lambda a:module.ActionPolicy.ALLOW))
    async def run():
        first=await module.diagnose_table(attempt_id='owner-table-schema-001',paths=Paths())
        assert first['status']=='TABLE_STRUCTURE_INCOMPLETE'
        second=await module.diagnose_table(attempt_id='owner-table-schema-001',paths=Paths())
        assert second['error_code']=='table_diagnostic_attempt_consumed'
        assert events==['owner_confirmed','loads','close','close']
    asyncio.run(run())


def test_poll_delayed_and_empty(monkeypatch):
    class Frame:
        count=0
        async def evaluate(self,*args):
            self.count+=1
            return {'overflow':False,'tables':[{'visible_row_count':int(self.count>2),'header_cell_count':2}]}
    class Executor:
        frame=Frame()
        async def guard(self):
            pass
        def frames(self):
            return [self.frame]
    async def run():
        ticks=iter([0,0,0.5,1.1])
        monkeypatch.setattr(module.time,'monotonic',lambda:next(ticks,2))
        # Do not patch the shared event-loop monotonic clock while it is sleeping.
        async def no_sleep(_):
            pass
        monkeypatch.setattr(module.asyncio,'sleep',no_sleep)
        tables,_,ready=await module.poll_tables(Executor())
        assert ready and tables[0]['visible_row_count']==1
        class Empty(Executor):
            def frames(self):
                return []
        assert not (await module.poll_tables(Empty(),timeout=0))[2]
    asyncio.run(run())
