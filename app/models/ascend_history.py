"""Observed Ascend export evidence, separate from active canonical shipments."""
from datetime import date as CalendarDate, datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field

from app.models.domain import Model


class HistoricalLocation(Model):
    name: str | None = None
    address: str | None = Field(default=None, repr=False)
    city: str | None = None
    state: str | None = None
    postal: str | None = None
    country: str | None = None
    date: CalendarDate | None = None
    local_datetime: datetime | None = None
    timezone: None = None  # No source zone: never attach an inferred offset.


class AscendHistoricalEvidence(Model):
    source_load_id: str = Field(min_length=1)
    raw_customer: str | None = None
    raw_carrier: str | None = None
    carrier_mc: str | None = None
    carrier_dot: str | None = None
    pickup: HistoricalLocation
    delivery: HistoricalLocation
    raw_equipment: str | None = None
    commodity: str | None = None
    weight: Decimal | None = None
    weight_unit: None = None
    client_mileage: Decimal | None = None
    carrier_mileage: Decimal | None = None
    truck_status: str | None = None
    drivers: str | None = Field(default=None, repr=False)
    power_unit: str | None = None
    trailer: str | None = None
    references: str | None = Field(default=None, repr=False)
    load_status: str | None = None
    branch: str | None = None
    notes: str | None = Field(default=None, repr=False)
    private_notes: str | None = Field(default=None, repr=False)
    created_at: AwareDatetime | None = None
    historical_total_income: Decimal
    historical_total_expenses: Decimal
    historical_gross_profit_loss: Decimal
    historical_margin_percent: Decimal
    historical_carrier_pay: None = None
    currency: None = None  # Dollar symbol alone is not an ISO currency declaration.


class AscendSchemaMapping(Model):
    version: Literal["ascend-csv-m4a-v1"] = "ascend-csv-m4a-v1"
    source_hash: str
    source_headers: list[str]
    columns: dict[str, str]
    local_date_formats: list[str] = ["%m/%d/%Y %H:%M", "%m/%d/%Y"]
    created_date_format: str = "ISO-8601 with explicit offset"
    status: Literal["PROPOSED"] = "PROPOSED"
    currency: None = None
    expenses_semantics: Literal["TOTAL_EXPENSES_NOT_CARRIER_PAY"] = "TOTAL_EXPENSES_NOT_CARRIER_PAY"


class RawCustomerIdentity(Model):
    id: str
    label: str
    sample_size: int
    source_load_ids: list[str]


class ProposedCustomerAliasGroup(Model):
    id: str
    raw_identity_ids: list[str]
    raw_labels: list[str]
    reason: str
    sample_size: int
    source_load_ids: list[str]
    status: Literal["PROPOSED"] = "PROPOSED"


class ApprovedCustomerIdentity(Model):
    id: str
    raw_identity_ids: list[str]
    approved_by: str
    approved_at: AwareDatetime


class ProposedEquipmentMapping(Model):
    raw_label: str
    proposed_family: str | None
    proposed_length_feet: int | None
    sample_size: int
    proposed_features: list[str] = Field(default_factory=list)
    status: Literal["PROPOSED"] = "PROPOSED"
