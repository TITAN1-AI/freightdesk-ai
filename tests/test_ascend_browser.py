import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.core.config import ROOT
from app.models.domain import ActionPolicy, AuthorizedIdentity, Role, utcnow
from app.policies.engine import PolicyEngine
from app.services.ascend_actions import AscendActionLedger, WriteIntent
from app.services.ascend_live import projected_summary
from app.services.ascend_reconciliation import reconcile
from app.services.mail_sync import digest
from app.services.store import Store
from executors.playwright.browser import AveryBrowserSession, BrowserExecutor
from integrations.ascend.adapter import AscendBrowserAdapter
from integrations.ascend.models import (
    FIELDS, AscendError, BrowserContract, ComparisonEvidence, FieldSelector, ReadGrant, Selector,
)


def field(name, optional=False):
    return FieldSelector(section='synthetic '+name,
        selectors=[Selector(kind='test_id', value=name)], optional=optional)


def contract():
    return BrowserContract(version='fixture-1', origin='https://ascend-fixture.invalid',
        account_url='https://ascend-fixture.invalid/account',
        exact_load_url='https://ascend-fixture.invalid/load/{load_number}',
        expected_company='Synthetic Booking Company', expected_account='synthetic-account-1',
        company=field('company'), account=field('account'), ready=field('ready'),
        fields={key:field(key, optional=key != 'load_number') for key in FIELDS},
        verified=True, verified_by='owner', verified_at=utcnow())


def grant(c):
    return ReadGrant(id='synthetic-grant-1', load_number='1752', contract_hash=digest(c.model_dump(mode='json')),
                     owner_authorized=True, expires_at=utcnow()+timedelta(minutes=5))


class Locator:
    def __init__(self, page, key):
        self.page, self.key = page, key

    async def count(self):
        return len(self.page.values.get(self.key, []))

    async def wait_for(self, **kwargs):
        if not self.page.values.get(self.key):
            raise RuntimeError('SYNTHETIC PRIVATE PAGE ERROR')

    async def inner_text(self):
        if self.page.crash:
            raise RuntimeError('SYNTHETIC COOKIE SECRET')
        self.page.reads.append(self.key)
        return self.page.values[self.key][0]

    input_value = inner_text


class Page:
    def __init__(self):
        self.url = 'about:blank'
        self.reads = []
        self.navigation = []
        self.crash = False
        self.values = {key:[value] for key,value in {'company':'Synthetic Booking Company',
            'account':'synthetic-account-1', 'ready':'Ready', 'load_number':'1752',
            'customer':'Synthetic Customer', 'customer_revenue':'$1,000.00', 'total_expenses':'$800.00',
            'gross_profit':'$200.00', 'gross_margin':'20.00%', 'driver_phone':'832-555-0199',
            'private_notes':'SYNTHETIC PRIVATE NOTE', 'pickup_appointment':'09/03/2024 11:00',
            'carrier_mc':' MC001234 '}.items()}

    async def goto(self, url, **kwargs):
        self.navigation.append(url)
        self.url = url

    def get_by_test_id(self, value):
        return Locator(self, value)

    def get_by_role(self, value, **kwargs):
        return Locator(self, kwargs.get('name', value))

    def get_by_label(self, value, **kwargs):
        return Locator(self, value)

    def locator(self, value):
        return Locator(self, value)


def reader(page=None, c=None, policies=None, running=lambda:True):
    page, c = page or Page(), c or contract()
    return AscendBrowserAdapter(BrowserExecutor(page), c,
        policies or PolicyEngine(ROOT/'config'/'policies.json'), running), page, c


def test_exact_read_typed_fields_unknowns_and_provenance():
    adapter, page, c = reader()
    observation = asyncio.run(adapter.read_load(grant(c)))
    assert observation.fields['customer_revenue'].normalized == '1000.00'
    assert observation.fields['total_expenses'].normalized == '800.00'
    assert observation.fields['carrier_mc'].raw_value == ' MC001234 '
    assert observation.fields['carrier_mc'].normalized == 'MC001234'
    assert observation.fields['commodity'].availability == 'MISSING'
    assert observation.fields['pickup_appointment'].normalization.endswith('no conversion')
    assert observation.fields['private_notes'].source_section == 'synthetic private_notes'
    assert observation.fields['driver_phone'].raw_value == '832-555-0199'
    assert '832-555' not in repr(observation) and not observation.live_validated
    assert len(page.navigation) == 2 and page.reads[:2] == ['company', 'account']


@pytest.mark.parametrize('change', ['company','account','ambiguous','missing','redirect','expired','unverified','grant_hash','policy','paused'])
def test_read_gates_before_shipment_data(change):
    page, c = Page(), contract()
    policies = PolicyEngine(ROOT/'config'/'policies.json')
    if change in {'company','account'}:
        page.values[change] = ['wrong tenant']
    if change == 'ambiguous':
        page.values['account'] *= 2
    if change == 'missing':
        page.values.pop('company')
    if change == 'redirect':
        async def redirect(url, **kwargs):
            page.url = 'https://wrong.invalid/account'
        page.goto = redirect
    if change == 'unverified':
        c.verified = False
    if change == 'policy':
        policies.rules['read_ascend'] = ActionPolicy.FORBIDDEN
    g = grant(c)
    if change == 'expired':
        g.expires_at = utcnow()-timedelta(seconds=1)
    if change == 'grant_hash':
        g.contract_hash = 'wrong'
    adapter, _, _ = reader(page, c, policies, lambda:change != 'paused')
    with pytest.raises(AscendError):
        asyncio.run(adapter.read_load(g))
    assert 'customer' not in page.reads


def test_exact_load_mismatch_stops_before_other_fields():
    adapter, page, c = reader()
    page.values['load_number'] = ['1753']
    with pytest.raises(AscendError, match='exact_load_mismatch'):
        asyncio.run(adapter.read_load(grant(c)))
    assert 'customer' not in page.reads


def test_selector_fallback_and_ambiguous_primary():
    page = Page()
    spec = FieldSelector(section='fixture', selectors=[Selector(kind='label', value='gone'),
        Selector(kind='role', value='heading', name='customer')])
    assert asyncio.run(BrowserExecutor(page).read(spec)) == 'Synthetic Customer'
    page.values['gone'] = ['x','x']
    with pytest.raises(AscendError, match='ambiguous_selector'):
        asyncio.run(BrowserExecutor(page).read(spec))


def test_crash_is_sanitized_and_never_retried():
    adapter, page, c = reader()
    page.crash = True
    with pytest.raises(AscendError, match='browser_read_failed_no_retry') as error:
        asyncio.run(adapter.read_load(grant(c)))
    assert 'SECRET' not in str(error.value)
    assert len(page.navigation) == 1 and adapter.executor.status == 'RECOVERY_REQUIRED'


def test_unmapped_fields_are_unavailable():
    c = contract()
    del c.fields['weight']
    adapter, _, _ = reader(c=c)
    observation = asyncio.run(adapter.read_load(grant(c)))
    assert observation.fields['weight'].availability == 'UNAVAILABLE'


def test_reconciliation_all_five_statuses_and_identity_gate():
    adapter, _, c = reader()
    o = asyncio.run(adapter.read_load(grant(c)))
    sources = [ComparisonEvidence(source='canonical', load_number='1752', identity_reconciled=True,
        observed_at=utcnow(), evidence_reference='synthetic-canonical',
        fields={'customer':'Synthetic Customer', 'carrier_mc':'different'}),
        ComparisonEvidence(source='Ascend history', load_number='1752', identity_reconciled=True,
            observed_at=utcnow(), evidence_reference='synthetic-history', fields={'customer':'Synthetic Customer'}),
        ComparisonEvidence(source='Outlook', load_number='1752', identity_reconciled=False,
            evidence_reference='unverified-mail', fields={'customer':'Synthetic Customer'})]
    rows = reconcile(o, sources)
    assert {r['status'] for r in rows} == {'MATCH','DIFFERENT','UNKNOWN','STALE','UNAVAILABLE'}
    assert all(r['status'] == 'UNAVAILABLE' for r in rows if r['comparison_source'] == 'Outlook')
    assert all('raw_vs_derived' in r and 'calculated_at' in r for r in rows)


def test_profile_and_authorization_boundary():
    session = AveryBrowserSession()
    assert str(session.profile) == r'C:\FreightDeskRuntime\Browser\booking-logistics\ascend'
    with pytest.raises(AscendError, match='owner_browser_authorization_required'):
        asyncio.run(session.launch(owner_authorized=False))


def test_all_production_write_interfaces_block_even_with_owner_payload():
    from integrations.ascend.models import OPERATIONS
    adapter, _, _ = reader()
    for operation in OPERATIONS:
        with pytest.raises(AscendError, match='production_writes_disabled'):
            asyncio.run(getattr(adapter, operation)({'approved':True}))


class FixtureTransport:
    fixture_only = True
    def __init__(self):
        self.calls = 0
        self.fields = {}
        self.version = 'v1'
        self.ambiguous = False
        self.crash = False
        self.identity = True

    async def verify_account(self):
        if not self.identity:
            raise AscendError('fixture_identity_failed')

    async def read_current(self, load_number):
        return {'load_number':load_number, 'version':self.version, 'fields':self.fields}

    async def mutate(self, operation, load_number, payload):
        self.calls += 1
        if self.crash:
            raise RuntimeError('SYNTHETIC SECRET')
        if not self.ambiguous:
            self.fields.update(payload)


@pytest.fixture
def ledger(tmp_path):
    store = Store(tmp_path/'ascend.sqlite3')
    yield AscendActionLedger(store, PolicyEngine(ROOT/'config'/'policies.json'), lambda load:True)
    store.close()


def intent():
    return WriteIntent(id='synthetic-action-1', load_number='1752', operation='update_status',
                       expected_version='v1', payload={'status':'Delivered'})


def approved(ledger, owner):
    action = ledger.enqueue(owner, intent())
    return ledger.approve(owner, action['id'], action['intent_hash'])


@pytest.mark.parametrize('failure', ['unapproved','paused','takeover','version','account','policy','production','payload_tamper'])
def test_write_preconditions(ledger, owner, failure):
    action = ledger.enqueue(owner, intent())
    if failure != 'unapproved':
        ledger.approve(owner, action['id'], action['intent_hash'])
    transport = FixtureTransport()
    if failure in {'paused','takeover'}:
        ledger.controls = lambda load:False
    if failure == 'version':
        transport.version = 'v2'
    if failure == 'account':
        transport.identity = False
    if failure == 'policy':
        ledger.policies.rules['update_status'] = ActionPolicy.FORBIDDEN
    if failure == 'production':
        transport.fixture_only = False
    if failure == 'payload_tamper':
        changed = ledger.store.get('booking-logistics','ascend_action',action['id'])
        changed['payload']['status'] = 'Changed'
        ledger.store.put('booking-logistics','ascend_action',action['id'],changed)
    with pytest.raises(AscendError):
        asyncio.run(ledger.execute_fixture(owner, action['id'], transport))
    assert transport.calls == 0


@pytest.mark.parametrize('result', ['success','ambiguous','crash'])
def test_write_postverify_uncertain_no_retry(ledger, owner, result):
    action = approved(ledger, owner)
    transport = FixtureTransport()
    transport.ambiguous, transport.crash = result == 'ambiguous', result == 'crash'
    finished = asyncio.run(ledger.execute_fixture(owner, action['id'], transport))
    assert finished['state'] == ('VERIFIED_FIXTURE' if result == 'success' else 'UNCERTAIN')
    asyncio.run(ledger.execute_fixture(owner, action['id'], transport))
    assert transport.calls == 1
    assert 'SECRET' not in json.dumps(ledger.store.timeline('booking-logistics'))


def test_inflight_crash_recovery_is_uncertain(ledger, owner):
    action = approved(ledger, owner)
    action.update(state='EXECUTING', attempts=1)
    ledger.store.put('booking-logistics','ascend_action',action['id'],action)
    transport = FixtureTransport()
    assert asyncio.run(ledger.execute_fixture(owner, action['id'], transport))['state'] == 'UNCERTAIN'
    assert transport.calls == 0


def test_owner_approval_not_model_or_other_tenant(ledger, owner):
    action = ledger.enqueue(owner, intent())
    for actor in [AuthorizedIdentity(id='model',tenant_id='booking-logistics',role=Role.SYSTEM),
                  AuthorizedIdentity(id='other',tenant_id='other',role=Role.OWNER)]:
        with pytest.raises(AscendError):
            ledger.approve(actor, action['id'], action['intent_hash'])
    with pytest.raises(AscendError):
        ledger.approve(owner, action['id'], 'unreviewed-hash')


def test_dashboard_private_fields_redacted(tmp_path):
    paths = SimpleNamespace(path=lambda *parts:tmp_path.joinpath(*parts))
    store = Store(paths.path('Data','booking-logistics','ascend.sqlite3'))
    adapter, _, c = reader()
    observation = asyncio.run(adapter.read_load(grant(c)))
    store.put('booking-logistics','ascend_observation','synthetic',observation)
    store.close()
    view = projected_summary(paths)
    assert '832-555-0199' not in json.dumps(view) and 'SYNTHETIC PRIVATE NOTE' not in json.dumps(view)
    assert len(view['loads']) == 1 and not view['live_validated']


def test_ascend_api_never_launches_browser_or_uses_demo_auth(client, monkeypatch):
    from app.core.runtime import RuntimePaths
    monkeypatch.setenv('FREIGHTDESK_LIVE_VIEW_TOKEN', 'x'*40)
    # Dedicated live bearer is still different from the test/demo owner bearer.
    assert client.get('/api/ascend/status').json()['live_validated'] is False
    assert client.get('/api/ascend/summary').status_code in {401,403}
    assert client.get('/assets/ascend.js').status_code == 200
    assert 'ascend' in str(RuntimePaths.from_environment().path('Browser','booking-logistics','ascend'))


def test_real_playwright_offline_dom_and_session_reuse(tmp_path):
    """A real browser, but all HTTP is fulfilled with synthetic HTML; no Ascend navigation."""
    async def run():
        from playwright.async_api import async_playwright
        c = contract()
        page_values = Page().values
        html = ''.join(f'<div data-testid="{key}">{values[0]}</div>' for key,values in page_values.items())
        async with async_playwright() as playwright:
            for iteration in range(2):
                context = await playwright.chromium.launch_persistent_context(str(tmp_path/'profile'),
                    channel='msedge', headless=True, offline=True, service_workers='block',
                    accept_downloads=False, downloads_path=str(tmp_path), args=['--disable-background-networking'])
                async def fixture(route):
                    await route.fulfill(status=200, content_type='text/html', body=html)
                await context.route('**/*', fixture)
                page = await context.new_page()
                adapter = AscendBrowserAdapter(BrowserExecutor(page), c, PolicyEngine(ROOT/'config'/'policies.json'))
                observation = await adapter.read_load(grant(c))
                assert observation.load_number == '1752'
                if iteration == 0:
                    await context.add_cookies([{'name':'synthetic_session', 'value':'fixture',
                        'url':c.origin, 'expires':(utcnow()+timedelta(hours=1)).timestamp()}])
                else:
                    assert any(cookie['name'] == 'synthetic_session' for cookie in await context.cookies())
                    async def summary(route):
                        await route.fulfill(json={'connection':{'status':'NOT_AUTHENTICATED',
                            'executor_status':'STOPPED', 'last_verified_company':None, 'last_successful_read':None},
                            'loads':[], 'pending_approvals':[], 'audit':[], 'production_writes':'BLOCKED'})
                    await context.route('**/api/ascend/summary', summary)
                    import re
                    panel = re.search(r'<section class="panel" id="ascend">.*?</section>',
                        (ROOT/'app'/'dashboard'/'index.html').read_text(encoding='utf-8')).group()
                    await page.set_content(panel)
                    await page.add_script_tag(path=str(ROOT/'app'/'dashboard'/'ascend.js'))
                    from playwright.async_api import expect
                    await expect(page.locator('#ascend-status')).to_have_text('NOT_AUTHENTICATED')
                    await expect(page.locator('#ascend-content')).to_contain_text('Production writes: BLOCKED')
                    await page.get_by_role('button', name='Refresh local evidence').click()
                    await expect(page.locator('#ascend-content')).to_contain_text('Last verified account: Unverified')
                await context.close()
    asyncio.run(run())


def test_allow_policy_runs_fixture_without_click_but_rates_stay_human_controlled(ledger, owner):
    ledger.policies.rules['update_status'] = ActionPolicy.ALLOW
    action = ledger.enqueue(owner, intent())
    assert action['state'] == 'QUEUED'
    transport = FixtureTransport()
    assert asyncio.run(ledger.execute_fixture(owner, action['id'], transport))['state'] == 'VERIFIED_FIXTURE'
    ledger.policies.rules['update_rates'] = ActionPolicy.ALLOW
    rate = intent().model_copy(update={'id':'synthetic-rate-1', 'operation':'update_rates',
                                      'payload':{'customer_revenue':'1000'}})
    assert ledger.enqueue(owner, rate)['state'] == 'AWAITING_APPROVAL'
    with pytest.raises(AscendError):
        asyncio.run(ledger.execute_fixture(owner, rate.id, transport))


def test_bounded_service_consumes_grant_and_tracks_reuse_without_writes(tmp_path, monkeypatch):
    import app.services.ascend_live as live
    paths = SimpleNamespace(path=lambda *parts:tmp_path.joinpath(*parts))
    launches = []
    class Session:
        def __init__(self, paths):
            pass
        async def launch(self, **kwargs):
            launches.append(True)
            return SimpleNamespace(pages=[Page()])
        async def readonly_network(self, origin):
            pass
        async def close(self):
            pass
    monkeypatch.setattr(live, 'AveryBrowserSession', Session)
    c, g = contract(), None
    g = grant(c)
    first = asyncio.run(live.bounded_read(c, g, paths=paths))
    assert first['connection']['session_reuse_proven'] is False
    with pytest.raises(AscendError):
        asyncio.run(live.bounded_read(c, g, paths=paths))
    assert len(launches) == 1
    assert live.projected_summary(paths)['connection']['last_successful_read'] is not None
    g.id = 'synthetic-grant-2'
    second = asyncio.run(live.bounded_read(c, g, paths=paths))
    assert second['connection']['session_reuse_proven'] is True
    assert not paths.path('Data','booking-logistics','history','history.sqlite3').exists()
    assert not paths.path('Data','booking-logistics','carrierview.sqlite3').exists()
    assert not paths.path('Data','booking-logistics','mail.sqlite3').exists()


def test_readonly_network_blocks_posts_other_origins_and_websockets():
    callbacks = {}
    class Context:
        async def route(self, pattern, callback):
            callbacks['http'] = callback
        async def route_web_socket(self, pattern, callback):
            callbacks['ws'] = callback
        async def set_offline(self, value):
            assert not value
    class Route:
        def __init__(self, method, url):
            self.request = SimpleNamespace(method=method, url=url)
            self.outcome = None
        async def abort(self):
            self.outcome = 'blocked'
        async def continue_(self):
            self.outcome = 'allowed'
    session = AveryBrowserSession()
    session.context = Context()
    asyncio.run(session.readonly_network('https://ascend-fixture.invalid'))
    for method, url, expected in [('GET','https://ascend-fixture.invalid/load','allowed'),
        ('POST','https://ascend-fixture.invalid/load','blocked'),
        ('PATCH','https://ascend-fixture.invalid/load','blocked'),
        ('GET','https://other.invalid/load','blocked')]:
        route = Route(method, url)
        asyncio.run(callbacks['http'](route))
        assert route.outcome == expected
    closed = []
    async def close():
        closed.append(True)
    asyncio.run(callbacks['ws'](SimpleNamespace(close=close)))
    assert closed


def test_dom_changes_during_snapshot_are_rejected():
    adapter, page, c = reader()
    original = page.get_by_test_id
    customer_reads = []
    def changing(key):
        locator = original(key)
        if key == 'customer':
            async def changed_text():
                customer_reads.append(True)
                return 'first' if len(customer_reads) == 1 else 'changed'
            locator.inner_text = changed_text
        return locator
    page.get_by_test_id = changing
    with pytest.raises(AscendError, match='provider_state_changed_during_read'):
        asyncio.run(adapter.read_load(grant(c)))


def test_launch_keeps_blank_tab_alive_before_closing_startup_pages(tmp_path, monkeypatch):
    import playwright.async_api
    events = []
    class StartupPage:
        async def close(self):
            assert events == ['new_blank_page']
            events.append('startup_closed')
    class Context:
        pages = [StartupPage()]
        async def new_page(self):
            events.append('new_blank_page')
        async def close(self):
            pass
    context = Context()
    class Chromium:
        async def launch_persistent_context(self, *args, **kwargs):
            assert kwargs['offline'] is True
            return context
    class Runtime:
        chromium = Chromium()
        async def stop(self):
            pass
    class Launcher:
        async def start(self):
            return Runtime()
    monkeypatch.setattr(playwright.async_api, 'async_playwright', Launcher)
    session = AveryBrowserSession(SimpleNamespace(path=lambda *parts:tmp_path.joinpath(*parts)))
    assert asyncio.run(session.launch(owner_authorized=True)) is context
    assert events == ['new_blank_page','startup_closed']
