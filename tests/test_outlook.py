from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.models.domain import ActionPolicy
from app.models.mail import MailExternalEvent
from app.services.mail_commands import VerifiedSender, owner_command
from app.services.mail_documents import classify_attachment, ingest_attachment
from app.services.mail_drafts import create_durable_draft, grounded_draft
from app.services.mail_intelligence import classify_text, correlate, extract_facts, extract_message
from app.services.mail_sync import MailSynchronizer, digest
from app.services.mail_view import mail_summary, sanitized
from app.services.store import Store
from integrations.outlook.adapter import GraphError, MicrosoftGraphMailAdapter
from integrations.outlook.auth import MicrosoftAuth, encrypted_cache
from integrations.outlook.config import ENTRA_CONFIGURED_PERMISSIONS, MicrosoftConfig, SCOPES
from integrations.outlook.models import Attachment, GraphPage, Message


@pytest.fixture
def anyio_backend():
    return "asyncio"


def config():
    return MicrosoftConfig(tenant_id=UUID(int=1), client_id=UUID(int=2))


def message(**changes):
    return Message.model_validate({"id": "fixture-m1", "subject": "Booking load 1752",
        "body": {"contentType": "text", "content": "ETA 2:30"},
        "receivedDateTime": "2026-09-03T10:00:00Z",
        "from": {"emailAddress": {"address": "owner@example.test", "name": "Owner"}}, **changes})


def adapter(handler):
    return MicrosoftGraphMailAdapter(config(), lambda: SecretStr("synthetic-test-token"),
                                     lambda _: None, httpx.MockTransport(handler))


@pytest.fixture
def mailstore(tmp_path):
    with_store = Store(tmp_path / "mail.sqlite3")
    yield with_store
    with_store.close()


def test_auth_defaults_no_network_or_send_scope():
    assert not config().network_authorized and not config().drafts_authorized
    assert SCOPES == ["User.Read", "Mail.ReadWrite", "MailboxSettings.Read"]
    assert 'Mail.Send' in ENTRA_CONFIGURED_PERMISSIONS and 'Mail.Send' not in SCOPES
    assert str(config().tenant_id) not in repr(config()) and str(config().client_id) not in repr(config())
    with pytest.raises(PermissionError):
        MicrosoftAuth(config()).application()
    with pytest.raises(ValidationError):
        MicrosoftConfig(tenant_id=UUID(int=1), client_id=UUID(int=2), mailbox="wrong@example.test")


def test_dpapi_cache_is_encrypted_synthetic_only(tmp_path):
    paths = SimpleNamespace(path=lambda *parts: tmp_path.joinpath(*parts))
    cache = encrypted_cache(paths)
    assert cache._persistence.is_encrypted
    cache._persistence.save('synthetic DPAPI cache proof')
    assert b'synthetic DPAPI cache proof' not in (tmp_path / 'Tokens/Microsoft/msal-cache.bin').read_bytes()
    assert cache._persistence.load() == 'synthetic DPAPI cache proof'


@pytest.mark.anyio
async def test_graph_profile_recent_and_header_boundaries():
    calls = []
    def handle(request):
        calls.append(request)
        assert 'IdType="ImmutableId"' in request.headers['Prefer']
        if request.url.path == '/v1.0/me':
            return httpx.Response(200, json={"id": "fixture", "mail": config().mailbox})
        return httpx.Response(200, json={"value": [message().model_dump(by_alias=True, mode="json")]})
    async with adapter(handle) as graph:
        with pytest.raises(PermissionError):
            await graph.list_recent_messages(5)
        await graph.get_mailbox_profile()
        rows, _ = await graph.list_recent_messages(5)
        assert rows[0].id == 'fixture-m1' and len(calls) == 2
        assert calls[-1].url.params['$top'] == '5'
        for send in (graph.send_message, graph.send_reply, graph.send_forward):
            with pytest.raises(PermissionError, match='APPROVAL_REQUIRED'):
                await send()
        assert len(calls) == 2


@pytest.mark.anyio
async def test_wrong_mailbox_stays_locked():
    async with adapter(lambda _: httpx.Response(200, json={'id': 'x', 'mail': 'wrong@example.test'})) as graph:
        with pytest.raises(PermissionError):
            await graph.get_mailbox_profile()
        assert not graph.mailbox_verified


@pytest.mark.parametrize('url', ['http://graph.microsoft.com/v1.0/me', '//evil.test/me',
    'https://evil.test/v1.0/me', 'https://graph.microsoft.com/v1.0/users/other'])
@pytest.mark.anyio
async def test_request_origin_and_resource_gate(url):
    async with adapter(lambda _: pytest.fail('Unexpected request')) as graph:
        graph.mailbox_verified = True
        with pytest.raises(PermissionError):
            await graph._request('GET', url, 'fixture')


@pytest.mark.parametrize('status,code', [(401,'authentication_required'), (403,'permission_denied'),
    (410,'delta_reset_required'), (429,'rate_limited'), (302,'http_error')])
@pytest.mark.anyio
async def test_safe_errors_no_retry(status, code):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={'error': {'message': 'PRIVATE RAW CONTENT'}}, headers={'Retry-After': '5'})
    async with adapter(handle) as graph:
        with pytest.raises(GraphError) as error:
            await graph.get_mailbox_profile()
        assert error.value.code == code and 'PRIVATE' not in str(error.value) and len(calls) == 1


@pytest.mark.parametrize('link', ['https://evil.test/x',
    'https://graph.microsoft.com/v1.0/me/mailFolders/sentitems/messages/delta?token=x'])
@pytest.mark.anyio
async def test_delta_rejects_cross_origin_or_folder_cursor(link):
    async with adapter(lambda _: httpx.Response(200, json={'value': [], '@odata.deltaLink': link})) as graph:
        graph.mailbox_verified = True
        with pytest.raises(PermissionError):
            await graph.delta_page()


@pytest.mark.anyio
async def test_all_read_interfaces_and_drafts_use_documented_paths():
    calls = []
    def handle(req):
        calls.append(req)
        if req.method == 'POST':
            assert '/send' not in req.url.path
            return httpx.Response(201, json={'id': 'draft-id', 'isDraft': True})
        if req.url.path.endswith('/m'):
            return httpx.Response(200, json={'id': 'm'})
        if req.url.path.endswith('/$value'):
            return httpx.Response(200, content=b'%PDF-fixture')
        return httpx.Response(200, json={'value': []})
    async with adapter(handle) as graph:
        graph.mailbox_verified = True
        await graph.list_mail_folders()
        await graph.get_message('m')
        await graph.search_messages('1752')
        await graph.get_conversation_messages("conversation'quoted")
        await graph.get_attachments('m')
        attachment = Attachment(id='a', name='a.pdf', size=12, contentType='application/pdf',
                                **{'@odata.type':'#microsoft.graph.fileAttachment'})
        assert await graph.download_attachment('m', attachment) == b'%PDF-fixture'
        payload = grounded_draft('owner@example.test')
        await graph.create_draft(payload)
        await graph.create_reply_draft('m', payload)
        await graph.create_forward_draft('m', payload)
        assert len(calls) == 9
        with pytest.raises(PermissionError):
            await graph.download_attachment('m', attachment.model_copy(update={'odata_type': '#microsoft.graph.referenceAttachment'}))


class DeltaFixture:
    def __init__(self, pages):
        self.pages = iter(pages)

    async def get_mailbox_profile(self):
        return None

    async def delta_page(self, folder, cursor):
        value = next(self.pages)
        if isinstance(value, Exception):
            raise value
        return GraphPage.model_validate(value)


@pytest.mark.anyio
async def test_delta_restart_dedup_partial_updates_and_folder_removal(mailstore):
    row = message().model_dump(mode='json', by_alias=True)
    sync = MailSynchronizer(mailstore)
    first = await sync.sync(DeltaFixture([{'value':[row], '@odata.nextLink':'next'}]), max_pages=1)
    assert first == {'processed': 1, 'round_complete': False}
    second = await sync.sync(DeltaFixture([{'value':[row], '@odata.deltaLink':'delta'}]))
    assert second['processed'] == 0
    await sync.sync(DeltaFixture([{'value':[{'id':row['id'], 'isRead':True, 'changeKey':'new'}], '@odata.deltaLink':'delta2'}]))
    assert len(mailstore.all('booking-logistics', 'mail_event')) == 1
    await sync.sync(DeltaFixture([{'value':[{'id':row['id'], '@removed':{'reason':'deleted'}}], '@odata.deltaLink':'delta3'}]))
    assert len(mailstore.all('booking-logistics','mail_message')) == 1
    assert not mailstore.all('booking-logistics','mail_membership')[0]['present']
    assert not mailstore.all('booking-logistics','shipment')


@pytest.mark.anyio
async def test_delta_failure_keeps_last_checkpoint(mailstore):
    sync = MailSynchronizer(mailstore)
    await sync.sync(DeltaFixture([{'value':[], '@odata.nextLink':'next'}]), max_pages=1)
    before = mailstore.all('booking-logistics','mail_checkpoint')
    with pytest.raises(GraphError):
        await sync.sync(DeltaFixture([GraphError('delta_reset_required', 410)]))
    assert before == mailstore.all('booking-logistics','mail_checkpoint')


@pytest.mark.anyio
async def test_delta_transaction_rolls_back_records_and_cursor(mailstore, monkeypatch):
    original = mailstore.put
    def fail_checkpoint(tenant, kind, key, value):
        if kind == 'mail_checkpoint':
            raise RuntimeError('fixture disk failure')
        return original(tenant, kind, key, value)
    monkeypatch.setattr(mailstore, 'put', fail_checkpoint)
    page = {'value':[message().model_dump(mode='json', by_alias=True)], '@odata.deltaLink':'delta'}
    with pytest.raises(RuntimeError):
        await MailSynchronizer(mailstore).sync(DeltaFixture([page]))
    assert not mailstore.all('booking-logistics','mail_event')
    assert not mailstore.all('booking-logistics','mail_checkpoint')
    assert mailstore.db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0] == 0


@pytest.mark.anyio
async def test_canonical_update_is_only_a_proposal(mailstore):
    await MailSynchronizer(mailstore).ingest_recent([message()])
    proposal = mailstore.all('booking-logistics', 'mail_update_proposal')[0]
    assert not proposal['verified'] and not proposal['applied']
    assert proposal['status'] == 'REVIEW_REQUIRED' and proposal['fields']['eta_text'] == '2:30'
    assert not mailstore.all('booking-logistics', 'shipment')


@pytest.mark.anyio
async def test_unverified_draft_response_is_uncertain():
    async with adapter(lambda _: httpx.Response(201, json={'id':'x','isDraft':False})) as graph:
        graph.mailbox_verified = True
        with pytest.raises(GraphError) as error:
            await graph.create_draft(grounded_draft('owner@example.test'))
        assert error.value.uncertain


@pytest.mark.parametrize('text,intent', [('please quote','CUSTOMER_QUOTE_REQUEST'),
    ('POD attached','POD'), ('signed rc','SIGNED_RATE_CONFIRMATION'), ('status 1752','OWNER_COMMAND'),
    ('breakdown','EXCEPTION_REPORT'), ('hello','UNKNOWN')])
def test_classification(text, intent):
    assert classify_text(text).intent == intent


def test_extraction_evidence_and_ambiguous_eta():
    msg = message(body={'content':'Driver is John Smith, 832-555-0199, truck 218 trailer 517 empty in Baytown and heading to pickup. ETA 2:30'})
    facts = extract_facts(msg)
    assert (facts.driver_name, facts.truck_number, facts.trailer_number) == ('John Smith','218','517')
    assert facts.current_location == 'Baytown' and facts.truck_status == 'EMPTY'
    assert facts.movement == 'EN_ROUTE_PICKUP' and facts.pickup_eta is None
    assert facts.ambiguities and all(e.verification == 'UNVERIFIED' for e in facts.evidence)
    text = msg.subject + '\n' + msg.body.content
    assert all(text[e.start:e.end] == e.source_text for e in facts.evidence)


@pytest.mark.anyio
async def test_model_cannot_invent_evidence():
    class FakeModel:
        async def generate(self, request):
            assert request.verified_facts == {} and len(request.untrusted_text) <= 4000
            return SimpleNamespace(structured_output={'customer':'Invented', 'evidence':[
                {'field':'customer','source_message_id':'fixture-m1','source_text':'Invented','start':0,
                 'end':8,'confidence':1,'verification':'VERIFIED'}]})
    assert (await extract_message(message(), 'booking-logistics', FakeModel())).customer is None


def test_correlation_requires_unambiguous_reference(plane):
    shipments = plane.store.all('booking-logistics','shipment')
    from app.models.domain import Shipment
    candidates = [Shipment.model_validate(row) for row in shipments]
    target = candidates[0]
    msg = message(subject='Booking load ' + target.id)
    assert correlate(msg, extract_facts(msg), candidates)['shipment_id'] == target.id
    duplicate = target.model_copy(update={'id':'duplicate', 'booking_load_id':target.id})
    assert correlate(msg, extract_facts(msg), [target,duplicate])['shipment_id'] is None
    multi = message(subject='Booking load 1752 and load 1753')
    assert correlate(multi, extract_facts(multi), candidates)['shipment_id'] is None


def test_attachment_guess_never_verifies_and_content_dedups(mailstore, tmp_path):
    assert classify_attachment(b'MZ executable','application/pdf','POD attached')['candidate_kind'] == 'OTHER'
    paths = SimpleNamespace(path=lambda *parts: tmp_path.joinpath(*parts))
    att = Attachment(id='a', name='../../POD.pdf', size=12, contentType='application/pdf')
    first = ingest_attachment(mailstore, message(), att, b'%PDF-fixture', paths=paths)
    second = ingest_attachment(mailstore, message(id='another'), att, b'%PDF-fixture', paths=paths)
    assert first['sha256'] == second['sha256'] and len(second['sources']) == 2
    assert not second['verified'] and second['scan_status'] == 'NOT_SCANNED'
    assert len(list(tmp_path.rglob('*.bin'))) == 1


@pytest.mark.anyio
async def test_durable_draft_uncertainty_never_retries(mailstore, owner):
    calls = []
    class Uncertain:
        config = config()
        async def create_draft(self, payload):
            calls.append(payload)
            raise GraphError('transport_error', uncertain=True)
    graph = Uncertain()
    payload = grounded_draft('owner@example.test')
    for _ in range(2):
        result = await create_durable_draft(mailstore, graph, owner, ActionPolicy.ALLOW, 'once', payload)
        assert result['state'] == 'UNCERTAIN'
    assert len(calls) == 1
    with pytest.raises(PermissionError):
        await create_durable_draft(mailstore, graph, owner, ActionPolicy.ALLOW, 'once', grounded_draft('other@example.test'))
    with pytest.raises(PermissionError):
        grounded_draft('owner@example.test', {'eta':{'value':'Tomorrow', 'verified':False}})


def test_email_owner_command_requires_bound_verified_proof(owner):
    event = MailExternalEvent(id='event', tenant_id=owner.tenant_id, mailbox=config().mailbox,
                              message=message(body={'content':'status 1752'}))
    proof = VerifiedSender(tenant_id=owner.tenant_id, address='owner@example.test', message_id=event.message.id,
                           content_hash=digest(event.message.model_dump(mode='json')), method='OWNER_REVIEW')
    def handler(actor, command):
        return 'sanitized status'
    with pytest.raises(PermissionError):
        owner_command(event, proof, {proof.address:owner}, handler)
    proof.verified = True
    assert owner_command(event, proof, {proof.address:owner}, handler)['executed']
    event.message.body.content = 'send money'
    with pytest.raises(PermissionError):
        owner_command(event, proof, {proof.address:owner}, handler)
    proof.content_hash = digest(event.message.model_dump(mode='json'))
    assert not owner_command(event, proof, {proof.address:owner}, handler)['executed']


@pytest.mark.anyio
async def test_mail_projection_sanitizes_and_demo_access_denied(mailstore, client):
    await MailSynchronizer(mailstore).ingest_recent([message(subject='832-555-0199 x@example.test https://private.test/signed $1234')])
    summary = mail_summary(mailstore)
    assert summary['messages_discovered'] == 1 and summary['live_validated'] is False
    subject = summary['recent'][0]['subject']
    assert '832' not in subject and 'private.test' not in subject and '1234' not in subject
    assert client.get('/api/mail/status').status_code == 200
    assert client.get('/api/mail/summary').status_code in (401,403)
    assert 'example.test' not in sanitized('x@example.test')


@pytest.mark.parametrize('flow', ['interactive', 'silent'])
def test_oauth_requests_explicit_current_scopes_only(flow):
    calls = []
    cfg = config().model_copy(update={'network_authorized':True})
    class FakeMSAL:
        def acquire_token_interactive(self, **kwargs):
            calls.append(kwargs)
            return {'access_token':'synthetic', 'id_token_claims':{'tid':str(cfg.tenant_id)}}
        def get_accounts(self):
            return [{'username':cfg.mailbox, 'realm':str(cfg.tenant_id)}]
        def acquire_token_silent(self, scopes, account):
            calls.append({'scopes':scopes})
            return {'access_token':'synthetic'}
    auth = MicrosoftAuth(cfg)
    auth._app = FakeMSAL()
    token = auth.login() if flow == 'interactive' else auth.get_token()
    assert isinstance(token, SecretStr)
    assert calls[0]['scopes'] == ['User.Read','Mail.ReadWrite','MailboxSettings.Read']
    assert 'extra_scopes_to_consent' not in calls[0]
    assert all('.default' not in scope and scope != 'Mail.Send' for scope in calls[0]['scopes'])


@pytest.mark.parametrize('zone', ['Central Standard Time','America/Chicago',None,'Unrecognized/Zone'])
@pytest.mark.anyio
async def test_settings_read_preserves_preferences_and_discards_extra_content(mailstore, zone):
    from app.services.mail_settings import read_mailbox_settings
    calls, audit = [], []
    def handle(req):
        calls.append(req)
        assert req.method == 'GET' and req.url.path == '/v1.0/me/mailboxSettings'
        assert req.url.params['$select'] == 'timeZone,language,dateFormat,timeFormat'
        return httpx.Response(200, json={'timeZone':zone, 'language':{'locale':'en-US'},
            'dateFormat':'MM/dd/yyyy', 'timeFormat':'h:mm tt',
            'automaticRepliesSetting':{'internalReplyMessage':'PRIVATE OOF TEXT'}})
    async with adapter(handle) as graph:
        graph.audit = audit.append
        with pytest.raises(PermissionError):
            await graph.get_mailbox_settings()
        assert not calls
        graph.mailbox_verified = True
        record = await read_mailbox_settings(graph, mailstore)
        assert len(calls) == 1 and record['settings']['timeZone'] == zone
        assert record['settings']['language']['locale'] == 'en-US'
        assert record['fixture'] and not record['live_validated'] and record['observed_at']
        assert 'PRIVATE' not in str(record) and 'PRIVATE' not in str(audit)
        assert 'en-US' not in str(audit)
        assert not mailstore.all('booking-logistics','shipment')
        assert extract_facts(message()).pickup_eta is None


@pytest.mark.anyio
async def test_settings_network_gate_precedes_token_access():
    def forbidden_token():
        pytest.fail('No token access allowed before owner OAuth authorization')
    async with MicrosoftGraphMailAdapter(config(), forbidden_token, lambda _: None) as graph:
        graph.mailbox_verified = True
        with pytest.raises(PermissionError, match='authentication boundary'):
            await graph.get_mailbox_settings()


@pytest.mark.parametrize('status', [401,403,429])
@pytest.mark.anyio
async def test_settings_error_does_not_overwrite_prior_context(mailstore, status):
    from app.services.mail_settings import read_mailbox_settings
    with mailstore.transaction():
        mailstore.put('booking-logistics','mail_settings','microsoft',{'prior':True})
    calls = []
    def handle(req):
        calls.append(req)
        return httpx.Response(status, json={'error':{'message':'PRIVATE'}})
    async with adapter(handle) as graph:
        graph.mailbox_verified = True
        with pytest.raises(GraphError):
            await read_mailbox_settings(graph, mailstore)
    assert len(calls) == 1 and mailstore.get('booking-logistics','mail_settings','microsoft') == {'prior':True}


@pytest.mark.anyio
async def test_invalid_settings_response_is_sanitized():
    async with adapter(lambda _: httpx.Response(200, json={'timeZone':{'private':'wrong type'}})) as graph:
        graph.mailbox_verified = True
        with pytest.raises(GraphError, match='invalid_mailbox_settings'):
            await graph.get_mailbox_settings()


@pytest.mark.parametrize('path', ['/v1.0/me/sendMail','/v1.0/me/messages/id/send',
    '/v1.0/me/messages/id/reply','/v1.0/me/messages/id/forward'])
@pytest.mark.anyio
async def test_provisioned_send_permission_cannot_enable_http_execution(path):
    async with adapter(lambda _: pytest.fail('Send must not reach HTTP transport')) as graph:
        graph.config.network_authorized = True
        graph.config.drafts_authorized = True
        graph.mailbox_verified = True
        assert 'Mail.Send' in ENTRA_CONFIGURED_PERMISSIONS
        with pytest.raises(PermissionError, match='disabled'):
            await graph._request('POST', path, 'send', draft=True)


def test_policy_and_provisioning_are_separate(plane):
    assert plane.policy('read_mailbox_settings') == ActionPolicy.ALLOW
    assert plane.policy('create_draft') == ActionPolicy.ALLOW
    for action in ('send_customer_email','send_carrier_email','send_dispatcher_email'):
        assert plane.policy(action) == ActionPolicy.APPROVAL_REQUIRED
