import asyncio
import json
import os
from types import SimpleNamespace

import pytest

from integrations.ascend import field_discovery as module
from integrations.ascend.models import AscendError, ComparisonEvidence


NAV = '<nav>'+''.join('<a href="#">'+n+'</a>' for n in
    ('Dashboard','Loads','Customers','Carriers','Locations','Reporting','Accounting','Settings'))+'</nav>'


def evidence():
    return [ComparisonEvidence(source=s, load_number='1752', identity_reconciled=True,
        evidence_reference='synthetic-source-'+s, fields={'load_number':'1752','customer':'Synthetic Customer'})
        for s in ('Ascend history', 'CarrierView')]


@pytest.mark.parametrize('scenario', ['read', 'search', 'duplicate', 'wrong_detail', 'submit', 'delete_link'])
def test_bounded_discovery_actual_browser_offline(tmp_path, scenario):
    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as runtime:
            context = await runtime.chromium.launch_persistent_context(str(tmp_path/'profile'), channel='msedge',
                headless=True, service_workers='allow', env={**os.environ, 'TEMP':str(tmp_path), 'TMP':str(tmp_path)})
            try:
                number = '1753' if scenario == 'wrong_detail' else '1752'
                detail = NAV+'<label for="load">Load Number</label><input id="load" value="'+number+'">'
                detail += '<label for="customer">Customer</label><input id="customer" value="Synthetic Customer">'
                detail += '<label for="private">Private notes SECRET_LABEL</label><textarea id="private">SECRET_PHONE_NOTE</textarea>'
                detail += '<button type="submit" onclick="window.forbidden=true">Save</button>'
                detail += '<button role="tab" type="button" aria-selected="true">General</button>'
                link = '<a href="/detail/1752">1752</a>'
                if scenario == 'duplicate':
                    link += '<a href="/detail/other">1752</a>'
                if scenario == 'submit':
                    link = '<form><button type="submit">1752</button></form>'
                if scenario == 'delete_link':
                    link = '<a href="/deleteLoad/1752">1752</a>'
                listing = NAV+'<table><tr><td>'+link+'</td></tr></table>'
                if scenario == 'search':
                    listing = NAV+'<input type="search" aria-label="Search loads" oninput="document.querySelector(\'#results\').innerHTML=\'<a href=/detail/1752>1752</a>\'"><div id="results"></div>'
                requests = []
                async def route(r):
                    requests.append((r.request.method, r.request.url))
                    if r.request.url.startswith('https://static-fixture.invalid'):
                        await r.fulfill(content_type='application/javascript', body='window.assetLoaded=true;')
                    elif '/framework-read' in r.request.url:
                        await r.fulfill(content_type='application/json', body='{}')
                    else:
                        body = detail if '/detail/' in r.request.url else listing
                        body += '<script src="https://static-fixture.invalid/app.js"></script><script>fetch("/framework-read",{method:"POST"})</script>'
                        await r.fulfill(content_type='text/html', body=body)
                await context.route('**/*', route)  # Every request synthetic; zero vendor networking.
                page = await context.new_page()
                await page.goto(module.ORIGIN+'/', wait_until='load')
                if scenario in {'read','search'}:
                    result = await module.discover_1752(page, evidence(), running=lambda:True)
                    encoded = result.model_dump_json()
                    assert result.source == 'live browser DOM' and result.validation_load == '1752'
                    assert sum(f.state == 'RECONCILED_FOR_1752' for f in result.fields) == 2
                    assert 'SECRET' not in encoded and 'Synthetic Customer' not in encoded
                    assert result.unknown_control_count == 1 and not result.live_validated
                    assert not await page.evaluate('!!window.forbidden')
                    assert any(method == 'POST' for method, url in requests)
                    assert any('static-fixture.invalid' in url for method, url in requests)
                else:
                    with pytest.raises(AscendError):
                        await module.discover_1752(page, evidence(), running=lambda:True)
                    assert not any('/deleteLoad' in url for method, url in requests)
            finally:
                await context.close()
    asyncio.run(run())


def row(field, value):
    return {'field':field, 'label':'Customer', 'control_type':'text', 'value_present':True,
        'raw':value, 'accessible_label':True, 'id_present':True, 'name_present':False, 'aria_label_present':False}


def test_ambiguous_conflicting_or_unproven_values_stay_unknown():
    refs = evidence()
    assert module.propose_fields([row('customer','Synthetic Customer')]*2, 'Details', refs)[0].state == 'UNKNOWN'
    refs[1].fields['customer'] = 'Other Customer'
    assert module.propose_fields([row('customer','Synthetic Customer')], 'Details', refs)[0].state == 'UNKNOWN'
    assert module.propose_fields([row('driver','Synthetic Driver')], 'Details', refs)[0].state == 'UNKNOWN'


def test_wrong_detail_identity_never_reads_other_values(monkeypatch):
    modes = []
    class Frame:
        url = module.ORIGIN+'/detail/1753'
        async def evaluate(self, script, args):
            modes.append(args['identityOnly'])
            return {'overflow':False, 'fields':[row('load_number','1753')]}
    page = SimpleNamespace(frames=[Frame()])
    executor = module.ReadOnly1752Executor(page, lambda:True)
    executor._opened = True
    async def guard():
        pass
    monkeypatch.setattr(executor, 'guard', guard)
    with pytest.raises(AscendError, match='detail_load_identity_unverified'):
        asyncio.run(executor.scan('Details'))
    assert modes == [True]


def test_same_process_owner_login_does_not_install_network_filters(monkeypatch):
    from integrations.ascend.session_continuity import owner_login_page
    events = []
    page = SimpleNamespace(url=module.ORIGIN+'/')
    class Context:
        pages = [page]
        async def set_offline(self, value):
            events.append(('offline', value))
    class Browser:
        async def launch(self, **kwargs):
            assert kwargs == {'owner_authorized':True, 'require_existing':True, 'normal_application_network':True}
            return Context()
        async def readonly_network(self, origin):
            pytest.fail('same-process run must not install request filters')
    monkeypatch.setattr('builtins.input', lambda _:None)
    assert asyncio.run(owner_login_page(Browser(), normal_application_network=True)) is page
    assert events == [('offline', False)]


def test_no_generic_write_or_model_driven_action_surface():
    assert all(not hasattr(module.ReadOnly1752Executor, action) for action in
        ('click','submit','save','create_load','delete','upload','send','execute_script','fill'))
    assert 'Save' not in module.TABS and 'Notes' not in module.TABS
    assert 'Private notes' not in module.LABELS and 'Driver Phone' not in module.LABELS
    assert 'SECRET' not in json.dumps(module.LABELS)
