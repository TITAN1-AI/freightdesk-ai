import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from integrations.ascend.identity import (
    IdentityConfig, OwnerAttestedIdentity, SessionDiagnostic, authenticated_session, observe_session,
)
from integrations.ascend.models import AscendError, ComparisonEvidence


@pytest.mark.parametrize('path,markers,login,expected', [
    ('/', ['Dashboard','Loads','Customers','Carriers'], False, True),
    ('/loads', ['Dashboard','Loads','Locations','Settings'], False, True),
    ('/login.html', ['Dashboard','Loads','Customers','Carriers'], False, False),
    ('/', ['Dashboard','Loads','Customers','Carriers'], True, False),
    ('/', [], False, False),
    ('/', ['Dashboard','Loads','Loads','Loads'], False, False),
    ('/', ['Customers','Carriers','Locations','Settings'], False, False),
])
def test_session_requires_independent_positive_and_negative_evidence(path, markers, login, expected):
    assert authenticated_session(path, markers, login) is expected


class Frame:
    def __init__(self, markers, login=False, origin='https://ascendtms.com'):
        self.url = origin+'/'
        self.markers, self.login = markers, login
    async def evaluate(self, script, approved):
        assert 'document.body' not in script and 'innerHTML' not in script
        return {'markers':self.markers, 'login':self.login}


class Page:
    def __init__(self, frames):
        self.frames = frames
        self.url = 'https://ascendtms.com/'
    async def title(self):
        return 'PRIVATE CUSTOMER: SECRET'


def test_diagnostic_allowlist_and_foreign_frames_cannot_prove_session():
    page = Page([Frame([], origin='https://other.invalid'), Frame(['Dashboard','Loads']),
                 Frame(['Customers','Carriers'])])
    result = asyncio.run(observe_session(page, IdentityConfig(origin='https://ascendtms.com')))
    assert not result.session_authenticated
    assert result.page_title == '[redacted unapproved title]'
    assert set(result.model_dump()) == {'current_path','page_title','authenticated_nav_markers',
                                       'login_form_present','session_authenticated'}
    page.frames = [Frame(['Dashboard','Loads','Customers','Carriers'])]
    assert asyncio.run(observe_session(page, IdentityConfig(origin='https://ascendtms.com'))).session_authenticated
    assert 'tenant_identity' not in result.model_dump()


def test_owner_attestation_cannot_be_other_tenant_origin_load_or_provider():
    for changed in [{'tenant_identity':'Other'}, {'origin':'https://other.invalid'},
                    {'load_number':'1753'}, {'tenant_identity_source':'PROVIDER_DOM'}, {'owner_authorized':False}]:
        with pytest.raises(ValueError):
            OwnerAttestedIdentity(**({'owner_authorized':True} | changed))


def test_real_browser_synthetic_navigation_and_login_detection(tmp_path):
    """Exercise the actual DOM predicate; all requests fulfilled with synthetic HTML."""
    async def run():
        import os

        from playwright.async_api import async_playwright
        async with async_playwright() as runtime:
            context = await runtime.chromium.launch_persistent_context(str(tmp_path/'profile'),
                channel='msedge', headless=True, service_workers='block',
                env={**os.environ, 'TEMP':str(tmp_path), 'TMP':str(tmp_path)})
            try:
                html = '<title>AscendTMS</title><nav>'+''.join(
                    '<a href="#">'+s+'</a>' for s in ['Dashboard','Loads','Customers','Carriers'])+'</nav>'
                async def fulfill(route):
                    await route.fulfill(content_type='text/html', body=html)
                await context.route('**/*', fulfill)
                page = await context.new_page()
                await page.goto('https://ascend-fixture.invalid/')
                config = IdentityConfig(origin='https://ascend-fixture.invalid')
                assert (await observe_session(page, config)).session_authenticated
                await page.set_content(html+'<form><input type="password"></form>')
                diagnostic = await observe_session(page, config)
                assert diagnostic.login_form_present and not diagnostic.session_authenticated
                await page.set_content('<title>AscendTMS</title><h1>Dashboard</h1>')
                assert not (await observe_session(page, config)).session_authenticated
                await page.goto('https://ascend-fixture.invalid/login.html')
                assert not (await observe_session(page, config)).session_authenticated
            finally:
                await context.close()
    asyncio.run(run())


@pytest.mark.parametrize('authenticated', [False, True])
def test_bootstrap_stops_at_failed_gate_and_consumes_attempt(tmp_path, monkeypatch, authenticated):
    from app.services import ascend_bootstrap as module
    navigation = []
    class Locator:
        @property
        def first(self):
            return self
        async def wait_for(self, **kwargs):
            pass
        async def count(self):
            return 1
        async def is_visible(self):
            return True
    class BrowserPage:
        async def goto(self, url, **kwargs):
            navigation.append(url)
        def get_by_role(self, *args, **kwargs):
            return Locator()
        def get_by_text(self, value, **kwargs):
            assert value == '1752' and kwargs['exact']
            return Locator()
    class Session:
        def __init__(self, paths):
            self.profile = Path(OwnerAttestedIdentity(owner_authorized=True).profile)
        async def launch(self, **kwargs):
            assert kwargs == {'owner_authorized':True, 'require_existing':True}
            return SimpleNamespace(pages=[BrowserPage()])
        async def readonly_network(self, origin):
            assert origin == 'https://ascendtms.com'
        async def close(self):
            pass
    async def observe(*args):
        return SessionDiagnostic(current_path='/', page_title='AscendTMS',
            authenticated_nav_markers=[], login_form_present=False, session_authenticated=authenticated)
    monkeypatch.setattr(module, 'AveryBrowserSession', Session)
    monkeypatch.setattr(module, 'observe_session', observe)
    monkeypatch.setattr(module, 'existing_evidence', lambda *args:[ComparisonEvidence(source=s,
        load_number='1752', identity_reconciled=True, evidence_reference='synthetic')
        for s in ['Ascend history','CarrierView']])
    paths = SimpleNamespace(path=lambda *parts:tmp_path.joinpath(*parts))
    result = asyncio.run(module.validate_1752(attempt_id='synthetic-attempt', owner_attested=True, paths=paths))
    assert result['tenant_identity_source'] == 'OWNER_ATTESTED'
    assert not result['provider_tenant_identity_verified'] and not result['load_fields_read']
    assert len(navigation) == (2 if authenticated else 1)
    assert result['exact_load_discovered'] is authenticated
    assert result['status'] == ('STOPPED_OBSERVED_LOAD_DOM_CONTRACT_REQUIRED' if authenticated else
                                'STOPPED_SESSION_NOT_AUTHENTICATED')
    with pytest.raises(FileExistsError):
        asyncio.run(module.validate_1752(attempt_id='synthetic-attempt', owner_attested=True, paths=paths))
    assert len(navigation) == (2 if authenticated else 1)
    for diagnostic in tmp_path.rglob('*-diagnostic.json'):
        assert len(json.loads(diagnostic.read_text())) == 5


def test_owner_attested_adapter_does_not_read_company_or_fabricate_provider_hash(monkeypatch):
    from integrations.ascend import identity
    from integrations.ascend.adapter import AscendBrowserAdapter
    from tests.test_ascend_browser import Page as FixturePage
    from tests.test_ascend_browser import contract, grant
    from executors.playwright.browser import BrowserExecutor
    from app.models.domain import ActionPolicy
    from integrations.ascend.models import BrowserContract

    data = contract().model_dump(mode='json') | {'origin':'https://ascendtms.com',
        'account_url':'https://ascendtms.com/', 'exact_load_url':'https://ascendtms.com/loads',
        'tenant_identity_source':'OWNER_ATTESTED', 'owner_attested_booking_logistics':True,
        'expected_company':'Booking Logistics', 'expected_account':'', 'company':None, 'account':None}
    c = BrowserContract.model_validate(data)
    page = FixturePage()
    async def observed(*args):
        return SessionDiagnostic(current_path='/loads', page_title='AscendTMS',
            authenticated_nav_markers=['Dashboard','Loads','Customers','Carriers'], login_form_present=False,
            session_authenticated=True)
    monkeypatch.setattr(identity, 'observe_session', observed)
    adapter = AscendBrowserAdapter(BrowserExecutor(page), c, SimpleNamespace(evaluate=lambda _:ActionPolicy.ALLOW))
    result = asyncio.run(adapter.read_load(grant(c)))
    assert result.tenant_identity_source == 'OWNER_ATTESTED' and result.account_hash == ''
    assert result.session_authenticated and not result.provider_tenant_identity_verified
    assert not result.session_reuse_proven and not result.live_validated
    assert 'company' not in page.reads and 'account' not in page.reads
    wrong = grant(c).model_copy(update={'load_number':'1753'})
    with pytest.raises(AscendError, match='exact_1752_only'):
        asyncio.run(adapter.read_load(wrong))
