"""Exact-load DOM reads, identity gates and blocked logical write interfaces."""
from decimal import InvalidOperation
from typing import Protocol
from urllib.parse import urlsplit

from app.models.domain import ActionPolicy, utcnow
from app.services.ascend_staging import decimal_value
from app.services.mail_sync import digest
from integrations.ascend.models import (
    FIELDS, AscendError, AscendFact, AscendObservation, BrowserContract, ReadGrant,
)


class AscendAdapter(Protocol):
    async def read_load(self, grant: ReadGrant) -> AscendObservation: ...
    async def create_load(self, request): ...
    async def update_load(self, request): ...
    async def assign_carrier(self, request): ...
    async def update_driver_info(self, request): ...
    async def update_truck_trailer(self, request): ...
    async def update_pickup_eta(self, request): ...
    async def update_delivery_eta(self, request): ...
    async def update_status(self, request): ...
    async def update_rates(self, request): ...
    async def add_note(self, request): ...
    async def upload_document(self, request): ...


def normalize_field(field, raw, page, section, now):
    normalized = raw.strip() if raw is not None else None
    availability = 'PRESENT' if normalized else 'MISSING'
    rule = 'trim_for_comparison_only; exact raw preserved'
    if normalized and field in {'customer_revenue', 'total_expenses', 'gross_profit', 'gross_margin', 'weight'}:
        try:
            # Unrecognized units/format stay raw and unparseable; do not guess currency or weight units.
            normalized = str(decimal_value(normalized, money=field in {
                'customer_revenue', 'total_expenses', 'gross_profit'}, percent=field == 'gross_margin'))
            rule = 'Decimal amount; live currency/unit unconfirmed; margin is percentage points'
        except (ValueError, InvalidOperation):
            normalized, availability = None, 'UNPARSEABLE'
            rule = 'source format/unit not established'
    if field in {'pickup_appointment', 'delivery_appointment'}:
        rule = 'raw local appointment text; timezone unknown; no conversion'
    return AscendFact(field=field, raw_value=raw, normalized=normalized, source_page=page,
        source_section=section, observed_at=now, availability=availability, normalization=rule)


class AscendBrowserAdapter:
    fixture_only = False

    def __init__(self, executor, contract: BrowserContract, policies, running=lambda: True):
        self.executor, self.contract, self.policies, self.running = executor, contract, policies, running

    def validate_url(self, url):
        parsed = urlsplit(url)
        origin = urlsplit(self.contract.origin)
        if (parsed.scheme != 'https' or parsed.username or parsed.password or
                origin.scheme != 'https' or origin.path not in {'', '/'} or origin.query or origin.fragment or
                f'{parsed.scheme}://{parsed.netloc}' != self.contract.origin.rstrip('/')):
            raise AscendError('unverified_browser_origin')

    async def verify_account(self):
        self.validate_url(self.executor.url)
        if self.contract.tenant_identity_source == 'OWNER_ATTESTED':
            from integrations.ascend.identity import IdentityConfig, observe_session
            diagnostic = await observe_session(self.executor.page, IdentityConfig(origin=self.contract.origin))
            if not diagnostic.session_authenticated:
                raise AscendError('authenticated_session_not_established')
            # No fabricated provider account hash: owner attestation is a different source.
            return 'Booking Logistics', ''
        company = await self.executor.read(self.contract.company)
        account = await self.executor.read(self.contract.account)
        if company != self.contract.expected_company or account != self.contract.expected_account or not account:
            raise AscendError('account_identity_mismatch_or_session_expired')
        return company, digest(account)

    async def read_load(self, grant: ReadGrant, *, use_current_session: bool = False):
        c = self.contract
        if c.tenant_identity_source == 'OWNER_ATTESTED' and grant.load_number != '1752':
            raise AscendError('owner_attested_bootstrap_exact_1752_only')
        if not c.verified or c.verified_by != 'owner' or not c.verified_at:
            raise AscendError('live_dom_contract_unverified')
        if grant.contract_hash != digest(c.model_dump(mode='json')) or grant.expires_at <= utcnow():
            raise AscendError('bounded_read_grant_invalid_or_expired')
        if self.policies.evaluate('read_ascend') != ActionPolicy.ALLOW or not self.running():
            raise AscendError('read_policy_or_pause_blocked')
        self.validate_url(c.account_url)
        load_url = c.exact_load_url.replace('{load_number}', grant.load_number)
        self.validate_url(load_url)
        if not use_current_session:
            await self.executor.navigate(c.account_url)
        await self.verify_account()  # Only identity selectors are read before this gate.
        await self.executor.navigate(load_url)
        company, account_hash = await self.verify_account()
        await self.executor.wait_ready(c.ready)
        raw_number = await self.executor.read(c.fields['load_number'])
        if raw_number is None or raw_number.strip() != grant.load_number:
            raise AscendError('exact_load_mismatch')
        now = utcnow()
        page = urlsplit(self.executor.url).path  # Never persist tokens/query/fragment in provenance.
        facts = {}
        for field in FIELDS:
            selector = c.fields.get(field)
            if selector is None:
                facts[field] = AscendFact(field=field, source_page=page, source_section='not mapped',
                    observed_at=now, availability='UNAVAILABLE', normalization='no verified selector')
                continue
            raw = raw_number if field == 'load_number' else await self.executor.read(selector)
            facts[field] = normalize_field(field, raw, page, selector.section, now)
        await self.verify_account()
        if (await self.executor.read(c.fields['load_number']) != raw_number or
                not self.running() or grant.expires_at <= utcnow()):
            raise AscendError('load_changed_or_read_authority_expired')
        # Reread all mapped values to reject an inconsistent page snapshot.
        for field, selector in c.fields.items():
            if await self.executor.read(selector) != facts[field].raw_value:
                raise AscendError('provider_state_changed_during_read')
        await self.verify_account()
        if not self.running() or grant.expires_at <= utcnow():
            raise AscendError('read_authority_expired')
        self.executor.status = 'READ_COMPLETE'
        return AscendObservation(load_number=grant.load_number, company=company, account_hash=account_hash,
            observed_at=now, contract_hash=grant.contract_hash,
            tenant_identity_source=c.tenant_identity_source, tenant_identity=company,
            session_authenticated=True, provider_tenant_identity_verified=c.tenant_identity_source == 'PROVIDER_DOM',
            version=digest({k: f.raw_value for k, f in facts.items()}), fields=facts)

    async def _blocked_write(self, request):
        raise AscendError('production_writes_disabled_separate_authorization_required')

    create_load = _blocked_write
    update_load = _blocked_write
    assign_carrier = _blocked_write
    update_driver_info = _blocked_write
    update_truck_trailer = _blocked_write
    update_pickup_eta = _blocked_write
    update_delivery_eta = _blocked_write
    update_status = _blocked_write
    update_rates = _blocked_write
    add_note = _blocked_write
    upload_document = _blocked_write
