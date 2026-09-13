import asyncio
import json
import os

from integrations.ascend import causal_identity_diagnostic as module
from tests.test_ascend_field_discovery import NAV


def test_causal_browser_fixtures(tmp_path):
    """All requests are fulfilled locally; all profiles live under the test runtime root."""
    async def run():
        from playwright.async_api import async_playwright
        cases = [
            ('opener_data', 'data-load-id="1755" data-target="#detail"', '', 'PROVIDER_OPENER_IDENTITY'),
            ('opener_event', 'onclick="openLoad(1755)" aria-controls="detail"', '', 'PROVIDER_OPENER_IDENTITY'),
            ('visible_detail', '', '<label for="lid">Load ID</label><input id="lid" readonly value="1755">', 'PROVIDER_DETAIL_FIELD'),
            ('hidden_detail', '', '<input type="hidden" name="load_id" value="1755">', 'PROVIDER_DETAIL_FIELD'),
            ('selection', 'aria-controls="detail"', '', 'PROVIDER_SELECTED_ROW_BINDING'),
            ('conflict', 'data-load-id="1755" data-target="#detail"', '<input name="load_id" value="1756">', 'CONFLICT'),
            ('multiple', 'data-load-id="1755" data-target="#detail"', '', 'AMBIGUOUS_DETAIL_CONTAINER'),
            ('multiple_inside_form', 'data-load-id="1755" data-target="#detail"', '', 'AMBIGUOUS_DETAIL_CONTAINER'),
            ('click_only', '', '', 'provider_binding_missing'),
            ('id_without_binding', 'data-load-id="1755"', '', 'provider_binding_missing'),
            ('query_redaction', 'data-load-id="1755" aria-controls="detail" data-token="PRIVATE_TOKEN"', '', 'PROVIDER_OPENER_IDENTITY'),
            ('private_values', 'data-load-id="1755" data-target="#detail"', '<input value="PRIVATE_DRIVER_PHONE"><textarea>PRIVATE_NOTE</textarea><input type="password" aria-label="Load ID" value="PRIVATE_PASSWORD">', 'PROVIDER_OPENER_IDENTITY'),
            ('unsafe_event', 'onclick="openLoad(1755); window.privateToken=\'PRIVATE_TOKEN\'" aria-controls="detail"', '', 'provider_binding_missing'),
            ('preexisting_panel', 'data-load-id="1755" data-target="#detail"', '', 'PROVIDER_OPENER_IDENTITY'),
            ('unapproved_id', 'data-load-id="1755" data-target="#detail"', '<input name="load_id" value="PRIVATE_ID">', 'CONFLICT'),
            ('unrelated_visible_panel', 'data-load-id="1755" data-target="#detail"', '', 'PROVIDER_OPENER_IDENTITY'),
            ('large_unrelated_dom', 'data-load-id="1755" data-target="#detail"', '', 'PROVIDER_OPENER_IDENTITY'),
        ]
        async with async_playwright() as runtime:
            context = await runtime.chromium.launch_persistent_context(str(tmp_path/'profile'), channel='msedge',
                headless=True, service_workers='block', env={**os.environ, 'TEMP':str(tmp_path), 'TMP':str(tmp_path)})
            await context.route('**/*', lambda r:r.fulfill(content_type='text/html', body='<title>AscendTMS</title>'))
            try:
                for name, attributes, fields, expected in cases:
                    page = await context.new_page()
                    await page.goto('https://ascendtms.com/loads?token=PRIVATE_QUERY')
                    href = '/loads?token=PRIVATE_QUERY' if name == 'query_redaction' else '#'
                    listing = NAV + '<table><thead><tr><th>Load ID</th></tr></thead><tbody><tr><td><a id="opener" href="'+href+'" '+attributes+'>1755</a></td></tr></tbody></table>'
                    if name == 'preexisting_panel':
                        listing += '<div role="dialog" id="detail" style="display:none"></div>'
                    if name == 'unrelated_visible_panel':
                        listing += '<div role="dialog"><input name="load_id" value="1756"></div>'
                    if name == 'large_unrelated_dom':
                        listing += '<form id="unrelated">' + '<input value="PRIVATE_VALUE">'*5000 + '</form>'
                    await page.set_content(listing)
                    if name == 'large_unrelated_dom':
                        await page.evaluate('''() => {for(const input of document.querySelectorAll('#unrelated input'))
                            Object.defineProperty(input,'value',{get(){throw Error('Unrelated input was read');}});}''')
                    await page.evaluate('''({fields, name}) => {
                        window.openLoad = () => {};
                        document.getElementById('opener').addEventListener('click', event => {
                            event.preventDefault();
                            if(name === 'selection') event.currentTarget.setAttribute('aria-selected','true');
                            let panel=document.getElementById('detail');
                            if(!panel){panel=document.createElement('div');panel.id='detail';panel.setAttribute('role','dialog');document.body.append(panel);}
                            panel.style.display='block';panel.innerHTML='<h2>Load Details</h2>'+fields;
                            if(name.startsWith('multiple')){
                                const second=panel.cloneNode(true);second.id='detail-two';document.body.append(second);
                                if(name==='multiple_inside_form'){
                                    const wrapper=document.createElement('form');document.body.append(wrapper);wrapper.append(panel,second);
                                }
                            }
                        });
                    }''', {'fields':fields, 'name':name})
                    observations = []
                    async def guard():
                        pass
                    observer = module.CausalObserver(page, guard, lambda s,m:observations.append((s,m)))
                    executor = module.TargetedReadExecutor(page, lambda:True, load_number='1755', authorized_loads=('1755',))
                    executor.guard = guard
                    await executor.open_1752(inspect_control=observer.prepare, before_click=observer.before_click)
                    after = await observer.snapshot()
                    result = module.decide(observer.before, after)
                    assert result.get('strategy_type', result.get('error_code')) == expected, (name, result)
                    changes = module.differential(observer.before, after)
                    assert any(c['change_type'] == ('newly_visible' if name == 'preexisting_panel' else 'newly_created') for c in changes)
                    encoded = json.dumps([observations, after, result, changes])
                    assert 'PRIVATE' not in encoded, name
                    assert 'openLoad(' not in encoded, name
                    if name == 'opener_data':
                        assert after[0]['control']['attributes']['data_attributes'][0] == {'name':'data-load-id', 'approved_value':'1755'}
                    if name == 'opener_event':
                        assert after[0]['control']['event']['safe_single_load_call']
                    if name in {'large_unrelated_dom', 'unrelated_visible_panel'}:
                        assert any(not c['identity_inspected'] for c in after[0]['containers'])
                    if name == 'visible_detail':
                        assert (await observer.finish(timeout=2))['state'] == 'VERIFIED'
                    await page.close()
            finally:
                await context.close()
    asyncio.run(run())


def test_runner_one_open_no_operational_extraction_or_other_phase(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'LIVE_EXECUTION_PREPARED', True)  # Fixture dependencies only.
    from tests.test_ops_cv_report import fixture
    manifest, candidates, _ = fixture()
    calls = []
    class Paths:
        def path(self, *parts):
            return tmp_path.joinpath(*parts)
    class Session:
        page = object()
        def __init__(self, paths):
            calls.append('construct')
        def running(self):
            return True
        async def confirm(self):
            calls.append('confirm')
        async def board(self, selected):
            selected()
            return {}
        async def detail(self, *args):
            raise AssertionError('Operational extraction forbidden')
        async def close(self):
            calls.append('close')
    class Executor:
        def __init__(self, *args, **kwargs):
            assert callable(kwargs.pop('observe'))
            assert kwargs == {'load_number':'1755', 'authorized_loads':('1755',)}
        async def guard(self):
            pass
        async def open_1752(self, *, inspect_control, before_click):
            await inspect_control(None, None)
            await before_click()
            calls.append('open1755')
    class Observer:
        def __init__(self, *args):
            pass
        async def prepare(self, *args):
            calls.append('prepare')
        async def before_click(self):
            calls.append('before')
        async def finish(self):
            return {'state':'VERIFIED', 'strategy_type':'PROVIDER_DETAIL_FIELD'}
    monkeypatch.setattr(module, 'load_manifest', lambda p:manifest)
    monkeypatch.setattr(module, 'board_candidates', lambda *a:candidates)
    monkeypatch.setattr(module, 'TargetedReadExecutor', Executor)
    old_store=module.Store(Paths().path('Data','booking-logistics','ascend','causal-identity-diagnostics.sqlite3'))
    old_store.put('booking-logistics','causal_grant','old-consumed',{'consumed':True})
    old_store.close()
    result = asyncio.run(module.run(Paths(), Session, Observer))
    assert result['status'] == 'CAUSAL_IDENTITY_DIAGNOSTIC_COMPLETE'
    assert calls == ['construct', 'confirm', 'prepare', 'before', 'open1755', 'close']
    assert not result['operational_extraction'] and not result['production_writes'] and not result['live_validated']
    result = asyncio.run(module.run(Paths(), Session, Observer))
    assert result['error_code'] == 'one_use_phase_consumed_no_retry'
    assert calls.count('construct') == 1
    assert len(list(tmp_path.rglob('*.sqlite3'))) == 1
    class FailurePaths:
        def path(self, *parts):
            return tmp_path.joinpath('failed-fixture', *parts)
    class FailedObserver(Observer):
        async def finish(self):
            return {'state':'UNKNOWN', 'error_code':'provider_binding_missing'}
    failed=asyncio.run(module.run(FailurePaths(), Session, FailedObserver))
    assert failed['pivot_required'] is True
    assert failed['error_code']=='provider_binding_missing'
    assert failed['execution_stage']=='IDENTITY_UNVERIFIED'


def test_unstable_dom_never_verifies(monkeypatch):
    observer = module.CausalObserver(None, None, lambda *a:None)
    observer.before = []
    async def guard():
        pass
    async def snapshot():
        return []
    observer.guard, observer.snapshot = guard, snapshot
    monkeypatch.setattr(module, 'decide', lambda *a:{'state':'VERIFIED'})
    assert asyncio.run(observer.finish(timeout=.01))['error_code'] == 'causal_dom_unstable'


def test_live_entrypoint_stopped_before_runtime_or_session(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'LIVE_EXECUTION_PREPARED', False)
    class Paths:
        def path(self, *args):
            raise AssertionError('No runtime creation authorized')
    assert asyncio.run(module.run(Paths()))['error_code'] == 'targeted_live_attempt_not_prepared'


def test_targeted_bounds_and_opener_checkpoint(tmp_path):
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as runtime:
            context = await runtime.chromium.launch_persistent_context(str(tmp_path/'profile'),channel='msedge',headless=True,
                service_workers='block',env={**os.environ,'TEMP':str(tmp_path),'TMP':str(tmp_path)})
            await context.route('**/*',lambda r:r.fulfill(content_type='text/html',body=''))
            try:
                for category in ['opener_attributes','visible_candidate_containers','container_attributes','identity_candidates']:
                    page=await context.new_page()
                    await page.goto('https://ascendtms.com/loads')
                    await page.set_content('<table><thead><tr><th>Load ID</th></tr></thead><tr><td><a href="#" id="opener">1755</a></td></tr></table>')
                    if category=='opener_attributes':
                        await page.evaluate("() => {for(let i=0;i<33;i++)document.querySelector('a').setAttribute('data-private-'+i,'PRIVATE');}")
                    if category=='visible_candidate_containers':
                        await page.evaluate("() => {for(let i=0;i<25;i++)document.body.insertAdjacentHTML('beforeend','<form>visible</form>');}")
                    if category=='container_attributes':
                        await page.evaluate("() => {const f=document.createElement('form');f.textContent='visible';for(let i=0;i<33;i++)f.setAttribute('data-private-'+i,'PRIVATE');document.body.append(f);}")
                    events=[]
                    async def guard():
                        pass
                    observer=module.CausalObserver(page,guard,lambda s,m:events.append((s,m)))
                    try:
                        await observer.prepare(page.locator('a'),page.locator('a'))
                        await observer.before_click()
                        if category=='identity_candidates':
                            await page.evaluate("() => document.body.insertAdjacentHTML('beforeend','<div role=dialog>'+ '<input name=load_id type=hidden value=1755>'.repeat(65)+'</div>')")
                            await observer.snapshot()
                        raise AssertionError('Expected a targeted bound')
                    except ValueError as error:
                        assert error.args==('targeted_causal_bound_exceeded',)
                    bound=events[-1][1]['bound']
                    assert bound['category']==category
                    assert (bound['measured'],bound['maximum'])=={
                        'opener_attributes':(35,32),'visible_candidate_containers':(25,24),
                        'container_attributes':(33,32),'identity_candidates':(66,64)}[category]
                    assert any(s=='OPENER_STRUCTURE' for s,m in events)==(category!='opener_attributes')
                    assert 'PRIVATE' not in json.dumps(events)
                    await page.close()
            finally:
                await context.close()
    asyncio.run(run())
