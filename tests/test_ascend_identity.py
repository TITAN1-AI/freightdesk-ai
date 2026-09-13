import asyncio
from types import SimpleNamespace

import pytest

from executors.playwright.browser import AveryBrowserSession
from integrations.ascend.identity import IdentityConfig, observe_identity
from integrations.ascend.models import AscendError


@pytest.mark.parametrize('origin', ['https://ascendtms.com/path','https://ascendtms.com/?token=x',
    'https://user:pass@ascendtms.com','http://ascendtms.com','https://ascendtms.com/#token',
    'https://ascendtms.com:443','https://ascendtms.com/ '])
def test_only_bare_https_origin_accepted(origin):
    with pytest.raises(ValueError):
        IdentityConfig(origin=origin)


def test_trailing_slash_normalized():
    assert IdentityConfig(origin='https://ascendtms.com/').origin == 'https://ascendtms.com'


def test_missing_profile_cannot_be_created_by_validation(tmp_path):
    session = AveryBrowserSession(SimpleNamespace(path=lambda *parts:tmp_path.joinpath(*parts)))
    with pytest.raises(AscendError, match='existing_ascend_profile_required'):
        asyncio.run(session.launch(owner_authorized=True, require_existing=True))
    assert not session.profile.exists()


class Locator:
    def __init__(self, count):
        self.amount = count
    async def count(self):
        return self.amount
    async def is_visible(self):
        return self.amount == 1


class Frame:
    def __init__(self, origin, present=True):
        self.url = origin+'/'
        self.present = present
        self.queries = 0
    def get_by_text(self, text, **kwargs):
        self.queries += 1
        assert text in {'BOOKING LOGISTICS LLC','Hello Manuel'}
        return Locator(int(self.present))
    def get_by_role(self, role, **kwargs):
        assert role == 'heading' and kwargs['name'] == 'Dashboard'
        return Locator(int(self.present))


def test_same_origin_frame_identity_and_foreign_frame_not_inspected():
    config = IdentityConfig(origin='https://ascendtms.com')
    foreign = Frame('https://other.invalid')
    page = SimpleNamespace(url=config.origin+'/', frames=[Frame(config.origin, False), Frame(config.origin), foreign])
    result = asyncio.run(observe_identity(page, config))
    assert result['identity_verified'] and foreign.queries == 0
    assert result['uninspected_frame_origins'] == ['https://other.invalid']


def test_ambiguous_account_frames_fail_closed():
    config = IdentityConfig(origin='https://ascendtms.com')
    page = SimpleNamespace(url=config.origin+'/', frames=[Frame(config.origin),Frame(config.origin)])
    assert not asyncio.run(observe_identity(page, config))['identity_verified']


def test_storage_presence_does_not_claim_authentication(tmp_path):
    session = AveryBrowserSession(SimpleNamespace(path=lambda *parts:tmp_path.joinpath(*parts)))
    (session.profile/'Default'/'Network').mkdir(parents=True)
    (session.profile/'Default'/'Network'/'Cookies').write_text('synthetic unread content')
    assert session.persistence_status()['cookie_database_present']
    assert not session.persistence_status()['cookie_values_read']
    assert not session.persistence_status()['authenticated_session_verified']
