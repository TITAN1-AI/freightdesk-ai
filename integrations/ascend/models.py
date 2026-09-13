"""Ascend browser contracts. No live selectors or API endpoints are assumed."""
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.models.domain import Model, utcnow

FIELDS = ('load_number', 'customer', 'customer_reference', 'status', 'origin', 'destination',
    'pickup_facility', 'delivery_facility', 'pickup_appointment', 'delivery_appointment',
    'equipment', 'commodity', 'weight', 'carrier', 'carrier_mc', 'carrier_dot', 'dispatcher',
    'driver', 'driver_phone', 'truck', 'trailer', 'customer_revenue', 'total_expenses',
    'gross_profit', 'gross_margin', 'notes', 'private_notes', 'tracking_status')
PRIVATE_FIELDS = {'driver', 'driver_phone', 'dispatcher', 'notes', 'private_notes'}
OPERATIONS = {'create_load', 'update_load', 'assign_carrier', 'update_driver_info',
    'update_truck_trailer', 'update_pickup_eta', 'update_delivery_eta', 'update_status',
    'update_rates', 'add_note', 'upload_document'}
POLICY_ACTIONS = {'update_driver_info': 'update_driver', 'update_truck_trailer': 'update_driver',
    'update_pickup_eta': 'update_load', 'update_delivery_eta': 'update_load', 'add_note': 'update_load'}


class AscendError(RuntimeError):
    """Only fixed application-authored codes; never propagate browser exception messages."""


class Selector(Model):
    kind: Literal['role', 'label', 'css', 'test_id']
    value: str = Field(min_length=1, max_length=200)
    name: str | None = Field(default=None, max_length=200)
    read: Literal['text', 'input'] = 'text'


class FieldSelector(Model):
    section: str = Field(min_length=1, max_length=80)
    selectors: list[Selector] = Field(min_length=1, max_length=3)
    optional: bool = True


class BrowserContract(Model):
    version: str
    origin: str
    account_url: str
    exact_load_url: str
    expected_company: str
    expected_account: str = Field(repr=False)
    company: FieldSelector | None = None
    account: FieldSelector | None = None
    ready: FieldSelector
    fields: dict[str, FieldSelector]
    verified: bool = False
    verified_by: Literal['owner'] | None = None
    verified_at: AwareDatetime | None = None
    tenant_identity_source: Literal['PROVIDER_DOM', 'OWNER_ATTESTED'] = 'PROVIDER_DOM'
    owner_attested_booking_logistics: bool = False

    @model_validator(mode='after')
    def fields_are_known(self):
        if self.tenant_identity_source == 'OWNER_ATTESTED':
            if (not self.owner_attested_booking_logistics or self.origin != 'https://ascendtms.com' or
                    self.account_url not in {'https://ascendtms.com', 'https://ascendtms.com/'} or
                    self.expected_company != 'Booking Logistics' or self.expected_account):
                raise ValueError('owner_attested_bootstrap_binding_invalid')
        if set(self.fields)-set(FIELDS) or 'load_number' not in self.fields:
            raise ValueError('ascend_contract_fields_invalid')
        if self.fields['load_number'].optional:
            raise ValueError('exact_load_identity_must_be_required')
        if self.ready.optional:
            raise ValueError('identity_and_ready_must_be_required')
        if self.tenant_identity_source == 'PROVIDER_DOM':
            if self.company is None or self.account is None or self.company.optional or self.account.optional:
                raise ValueError('identity_and_ready_must_be_required')
            if self.company.selectors == self.account.selectors:
                raise ValueError('independent_account_identity_required')
        return self


class ReadGrant(Model):
    tenant_id: Literal['booking-logistics'] = 'booking-logistics'
    load_number: str = Field(pattern=r'^\d{1,20}$')
    contract_hash: str
    owner_authorized: Literal[True]
    expires_at: AwareDatetime
    max_reads: Literal[1] = 1
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')


class AscendFact(Model):
    field: str
    raw_value: str | None = Field(default=None, repr=False)
    normalized: str | None = Field(default=None, repr=False)
    source_page: str
    source_section: str
    observed_at: AwareDatetime
    availability: Literal['PRESENT', 'MISSING', 'UNAVAILABLE', 'UNPARSEABLE']
    normalization: str
    raw_vs_derived: Literal['provider_fact_with_explicit_normalization'] = 'provider_fact_with_explicit_normalization'


class AscendObservation(Model):
    provider: Literal['AscendTMS'] = 'AscendTMS'
    tenant_id: Literal['booking-logistics'] = 'booking-logistics'
    actor: Literal['FreightDesk/Avery'] = 'FreightDesk/Avery'
    session_class: Literal['Avery operational browser session'] = 'Avery operational browser session'
    load_number: str
    company: str
    account_hash: str
    observed_at: AwareDatetime = Field(default_factory=utcnow)
    contract_hash: str
    version: str
    fields: dict[str, AscendFact] = Field(repr=False)
    session_reuse_proven: bool = False
    live_validated: bool = False
    tenant_identity_source: Literal['PROVIDER_DOM', 'OWNER_ATTESTED'] = 'PROVIDER_DOM'
    tenant_identity: str | None = None
    session_authenticated: bool = False
    provider_tenant_identity_verified: bool = False


class ComparisonEvidence(Model):
    source: Literal['canonical', 'CarrierView', 'Outlook', 'Ascend history']
    load_number: str
    identity_reconciled: bool = False
    observed_at: AwareDatetime | None = None
    evidence_reference: str
    fields: dict[str, str | None] = Field(default_factory=dict, repr=False)
