import asyncio
import json
import os

import pytest

from integrations.ascend import detail_identity_diagnostic as module


@pytest.mark.parametrize('body,path,expected',[
    ('<label for="id">Load ID</label><input id="id" value="1755">','/loads','VERIFIED'),
    ('','/loads/1755','VERIFIED'),
    ('<input type="hidden" name="load_id" value="1755">','/loads','VERIFIED'),
    ('<label for="id">Load ID</label><input id="id" value="1755"><h1>Load #1755</h1>','/loads/1755','VERIFIED'),
    ('<h1>Load #1756</h1>','/loads/1755','UNKNOWN'),
    ('<label>Customer</label><div>Same customer and lane</div>','/loads','UNKNOWN'),
    ('<h1>Load #1756</h1>','/loads','UNKNOWN'),
    ('<input name="load_id" value="1755"><input name="load_id" value="1755">','/loads','UNKNOWN'),
    ('<input name="load_id" value="SECRET_PHONE_TOKEN">','/loads','UNKNOWN'),
])
def test_identity_strategies_browser_fixture(tmp_path,body,path,expected):
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as runtime:
            context=await runtime.chromium.launch_persistent_context(str(tmp_path/'profile'),channel='msedge',headless=True,
                env={**os.environ,'TEMP':str(tmp_path),'TMP':str(tmp_path)})
            await context.route('**/*',lambda r:r.fulfill(content_type='text/html',body='<title>PRIVATE_CUSTOMER</title>'+body))
            try:
                page=await context.new_page()
                await page.goto(module.ORIGIN+path+'?session=SECRET_QUERY_TOKEN')
                signals=(await page.evaluate(module.SCAN,sorted(module.APPROVED)))['signals']
                meta=module.path_metadata(page.url)
                result=module.decide(signals,meta,{'path':path,'row_load_id':'1755'})
                assert result['state']==expected
                assert 'SECRET' not in json.dumps([signals,meta,result])
                if expected=='UNKNOWN' and '1756' in body:
                    assert result['error_code']=='conflicting_identity_signals'
            finally:
                await context.close()
    asyncio.run(run())


def test_ambiguous_route_requires_observed_row_link():
    assert module.decide([],module.path_metadata(module.ORIGIN+'/loads/1755'),{})['error_code']=='ambiguous_identity_route'
    assert module.path_metadata(module.ORIGIN+'/private/SECRET?token=SECRET')['path']=='[redacted path]'


def test_identity_requires_stable_observation_before_timeout():
    class Frame:
        url=module.ORIGIN+'/loads'
        async def evaluate(self,*args):
            return {'overflow':False,'signals':[{'kind':'named_input','candidate_value':'1755',
                'unapproved_value':False,'selector':'input'}]}
    class Page:
        url=module.ORIGIN+'/loads'
        frames=[Frame()]
        async def title(self):
            return 'PRIVATE_TITLE'
    async def guard():
        pass
    observations=[]
    result=asyncio.run(module.inspect(Page(),guard,{},lambda *args:observations.append(args),timeout=0))
    assert result['decision']['error_code']=='detail_identity_unstable'
    assert 'PRIVATE' not in json.dumps(observations)


def test_single_load_runner_never_reads_operational_fields(tmp_path,monkeypatch):
    from tests.test_ops_cv_report import fixture
    manifest,candidates,_=fixture()
    calls=[]
    class Paths:
        def path(self,*parts):
            return tmp_path.joinpath(*parts)
    class Session:
        page=type('Page',(),{'url':module.ORIGIN+'/loads'})()
        def running(self):
            return True
        async def confirm(self):
            calls.append('confirm')
        async def board(self,selected):
            selected()
            return {}
        async def close(self):
            calls.append('close')
        async def detail(self,*args):
            raise AssertionError('Operational extraction forbidden')
    class Executor:
        def __init__(self,*args,**kwargs):
            assert kwargs['load_number']=='1755' and kwargs['authorized_loads']==('1755',)
        async def guard(self):
            pass
        async def open_1752(self,before_open):
            before_open({'tag':'A','href':'/loads/1755?token=PRIVATE_TOKEN','id_present':True,'name_present':False,'data_attribute_count':0})
            calls.append('open1755')
    async def inspect(*args):
        return {'decision':{'state':'VERIFIED','strategy':{'kind':'visible_field','selector':'input'},'supporting_signal_count':0}}
    monkeypatch.setattr(module,'load_manifest',lambda p:manifest)
    monkeypatch.setattr(module,'LocalSession',lambda p:Session())
    monkeypatch.setattr(module,'board_candidates',lambda *args:candidates)
    monkeypatch.setattr(module,'ReadOnly1752Executor',Executor)
    monkeypatch.setattr(module,'inspect',inspect)
    result=asyncio.run(module.run(Paths()))
    assert result['status']=='IDENTITY_DIAGNOSTIC_COMPLETE'
    assert calls==['confirm','open1755','close']
    assert 'PRIVATE' not in json.dumps(result)
    assert not Paths().path('Data','booking-logistics','operations','operations.sqlite3').exists()
