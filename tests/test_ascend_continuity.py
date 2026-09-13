import asyncio
import json
from types import SimpleNamespace

import pytest

from integrations.ascend import session_continuity as module


def metadata(authenticated=True, session_entries=2):
    return {'first_party_cookie_count':3, 'session_only_cookie_count':2, 'persistent_cookie_count':1,
        'first_party_cookie_future_expiry':True, 'local_storage_entry_count':4,
        'session_storage_entry_count':session_entries, 'service_worker_registration_count':0,
        'body_text_length':100, 'authenticated_navigation_marker_count':8,
        'current_path':'/', 'session_authenticated':authenticated}


def test_cookie_metadata_never_retains_names_values_or_timestamps():
    result = module.aggregate_cookies([
        {'domain':'.ascendtms.com', 'expires':2000, 'name':'SECRET_NAME', 'value':'SECRET_VALUE'},
        {'domain':'ascendtms.com', 'expires':-1, 'name':'SECRET_NAME', 'value':'SECRET_VALUE'},
        {'domain':'unrelated.invalid', 'expires':4000, 'name':'SECRET_NAME', 'value':'SECRET_VALUE'}], 1000)
    assert result == {'first_party_cookie_count':2, 'session_only_cookie_count':1,
                     'persistent_cookie_count':1, 'first_party_cookie_future_expiry':True}
    assert 'SECRET' not in json.dumps(result)


def test_metadata_only_storage_and_session_probe(monkeypatch):
    class Context:
        async def cookies(self):
            return [{'domain':'ascendtms.com','expires':-1, 'name':'SECRET', 'value':'SECRET'}]
    class Page:
        url = module.ORIGIN+'/?token=SECRET'
        async def evaluate(self, script):
            assert 'localStorage.length' in script and 'sessionStorage.length' in script
            assert 'getItem' not in script and 'document.cookie' not in script
            return {'local_storage_entry_count':2, 'session_storage_entry_count':1,
                    'service_worker_registration_count':0, 'body_text_length':30}
    async def observe(*args):
        return SimpleNamespace(authenticated_nav_markers=['Dashboard','Loads'], session_authenticated=False)
    monkeypatch.setattr(module, 'observe_session', observe)
    result = asyncio.run(module.auth_metadata(Context(), Page()))
    assert result['current_path'] == '/' and result['first_party_cookie_count'] == 1
    assert 'SECRET' not in json.dumps(result)


def test_comparison_flags_loss_without_claiming_cause_or_auth_reuse():
    result = module.compare_auth(metadata(), metadata(False, 0))
    assert result['session_storage_loss_observed']
    assert not result['authentication_survived_reopen'] and not result['causality_established']
    assert result['count_delta_after_minus_before']['session_storage_entry_count'] == -2
    before = metadata() | {'local_storage_entry_count':None}
    assert module.compare_auth(before, metadata())['count_delta_after_minus_before']['local_storage_entry_count'] is None


def test_render_signals_only_counts_and_sanitized_redirect_paths():
    class Page:
        def on(self, *args):
            pass
        def remove_listener(self, *args):
            pass
        async def evaluate(self, script):
            return {'script_element_count':3, 'stylesheet_count':2}
    signals = module.RenderSignals(Page())
    signals.console(SimpleNamespace(type='error', text='SECRET'))
    signals.error(Exception('SECRET'))
    for kind, url in [('script','https://private.invalid/app.js?token=SECRET'),
                      ('font','https://private.invalid/font?token=SECRET'),
                      ('fetch',module.ORIGIN+'/undocumented?token=SECRET')]:
        signals.failed(SimpleNamespace(resource_type=kind, url=url))
    first = SimpleNamespace(url=module.ORIGIN+'/login.html?token=SECRET', redirected_from=None)
    response = SimpleNamespace(status=200, request=SimpleNamespace(url=module.ORIGIN+'/?token=SECRET', redirected_from=first))
    result = asyncio.run(signals.summary(response))
    assert result['redirect_path_chain'] == ['/login.html','/']
    assert result['failed_resource_origin_counts'] == {'other-origin-1':2, 'ascendtms.com':1}
    assert result['requestfailed_by_resource_type'] == {'script':1, 'font':1, 'fetch':1}
    assert result['javascript_console_error_count'] == result['pageerror_count'] == 1
    assert 'SECRET' not in json.dumps(result) and 'private.invalid' not in json.dumps(result)
    signals.detach()
    assert not signals.origin_ids


def test_owner_confirmation_keeps_exact_context_open(monkeypatch):
    events = []
    page = SimpleNamespace(url=module.ORIGIN+'/')
    class Context:
        pages = [page]
        async def set_offline(self, value):
            events.append(('offline', value))
    class Browser:
        async def launch(self, **kwargs):
            assert kwargs == {'owner_authorized':True, 'require_existing':True}
            events.append('launch')
            return Context()
        async def readonly_network(self, origin):
            events.append('readonly')
    monkeypatch.setattr('builtins.input', lambda _:events.append('owner_confirmed'))
    assert asyncio.run(module.owner_login_page(Browser())) is page
    assert events == ['launch', ('offline', False), 'owner_confirmed', 'readonly']


@pytest.mark.parametrize('authenticated', [True, False])
def test_same_process_wrapper_never_relaunches_or_closes_before_read(tmp_path, monkeypatch, authenticated):
    from app.services import ascend_bootstrap
    events = []
    context = object()
    page = SimpleNamespace(context=context)
    class Browser:
        async def close(self):
            events.append('close')
    browser = Browser()
    browser.context = context
    async def login(actual, **kwargs):
        assert actual is browser
        assert kwargs == {'normal_application_network':True}
        events.append('owner_login')
        return page
    async def observe(actual_page, config):
        assert actual_page is page
        return SimpleNamespace(session_authenticated=authenticated)
    async def read(**kwargs):
        assert kwargs['existing_browser'] is browser and kwargs['existing_page'] is page
        assert events == ['owner_login']
        events.append('read')
        return {'status':'READ_AND_RECONCILIATION_COMPLETE'}
    monkeypatch.setattr(module, 'checked_browser', lambda _:browser)
    monkeypatch.setattr(module, 'owner_login_page', login)
    monkeypatch.setattr(module, 'observe_session', observe)
    monkeypatch.setattr(ascend_bootstrap, 'validate_1752', read)
    paths = SimpleNamespace(path=lambda *parts:tmp_path.joinpath(*parts))
    result = asyncio.run(module.login_validate_1752(attempt_id='synthetic-same-process', paths=paths))
    assert events == (['owner_login','read','close'] if authenticated else ['owner_login','close'])
    assert not result['persistent_cross_process_session_reuse']


def test_reserved_attempt_rejected_before_browser_launch(monkeypatch):
    monkeypatch.setattr(module, 'checked_browser', lambda _:pytest.fail('must not launch'))
    with pytest.raises(module.AscendError, match='reserved_load_attempt'):
        asyncio.run(module.login_validate_1752(attempt_id='owner-bootstrap-1752-20260910-02'))


def test_continuity_reopens_once_and_saves_before_after_without_grants(tmp_path, monkeypatch):
    events = []
    class Page:
        async def goto(self, url, **kwargs):
            assert url == module.ORIGIN+'/'
            events.append('root')
    page = Page()
    class Browser:
        context = SimpleNamespace(pages=[page])
        async def launch(self, **kwargs):
            assert kwargs['require_existing']
            events.append('reopen')
            return self.context
        async def close(self):
            events.append('close')
        async def readonly_network(self, origin):
            pass
    browser = Browser()
    async def login(_):
        events.append('manual_login')
        return page
    counts = iter([metadata(), metadata(False, 0)])
    async def auth(*args):
        return next(counts)
    async def poll(*args):
        return {'session_authenticated_recommended':False}
    class Signals:
        def __init__(self, page):
            pass
        async def summary(self, response):
            return {'top_level_document_http_status':200}
        def detach(self):
            pass
    monkeypatch.setattr(module, 'checked_browser', lambda _:browser)
    monkeypatch.setattr(module, 'owner_login_page', login)
    monkeypatch.setattr(module, 'auth_metadata', auth)
    monkeypatch.setattr(module, 'poll_structure', poll)
    monkeypatch.setattr(module, 'RenderSignals', Signals)
    paths = SimpleNamespace(path=lambda *parts:tmp_path.joinpath(*parts))
    result = asyncio.run(module.diagnose_continuity(paths=paths))
    assert events == ['manual_login', 'close', 'reopen', 'root', 'close']
    assert result['comparison']['session_storage_loss_observed'] and not result['load_attempt_consumed']
    assert len(list(tmp_path.rglob('continuity-*.json'))) == 2
    assert not list(tmp_path.rglob('*claim*'))


def test_same_session_adapter_does_not_reload_account_root():
    from tests.test_ascend_browser import reader, grant
    adapter, page, contract = reader()
    page.url = contract.exact_load_url.replace('{load_number}', '1752')
    result = asyncio.run(adapter.read_load(grant(contract), use_current_session=True))
    assert page.navigation == [contract.exact_load_url.replace('{load_number}', '1752')]
    assert result.load_number == '1752' and not result.session_reuse_proven
