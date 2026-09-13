from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field

from app.models.domain import Model


class HistoricalLoad(Model):
    load_number: str = Field(min_length=1, max_length=100)
    customer: str | None = None
    customer_reference: str | None = None
    origin: str | None = None
    destination: str | None = None
    pickup_date: date | None = None
    delivery_date: date | None = None
    equipment: str | None = None
    commodity: str | None = None
    weight: Decimal | None = None
    customer_revenue: Decimal | None = None
    carrier_pay: Decimal | None = None
    gross_margin: Decimal | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    carrier: str | None = None
    carrier_mc: str | None = None
    carrier_dot: str | None = None
    status: str | None = None
    driver: str | None = None
    truck: str | None = None
    trailer: str | None = None
    notes: str | None = Field(default=None, repr=False)
    broker: str | None = None
    created_date: date | None = None
    pickup_facility: str | None = None
    delivery_facility: str | None = None


class HistoricalProvenance(Model):
    source_system: str
    source_identifier: str
    source_load_id: str
    imported_at: AwareDatetime
    original_timestamp: AwareDatetime | None = None
    source_hash: str
    source_version: str
    normalization_status: Literal["VALID", "REVIEW_REQUIRED", "INVALID"]


class SchemaMapping(Model):
    columns: dict[str, str]
    date_formats: dict[str, str] = Field(default_factory=dict)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    reviewed_by: str = Field(min_length=1)
    reviewed: bool = False


class RateHistorySummary(Model):
    metric: str
    currency: str
    sample_size: int
    minimum: Decimal | None = None
    median: Decimal | None = None
    average: Decimal | None = None
    maximum: Decimal | None = None
    date_from: date | None = None
    date_to: date | None = None
    source_records: list[str]
    calculated_at: AwareDatetime
    historical_only: bool = True


class DerivedProfile(Model):
    kind: Literal["CustomerProfile", "LaneProfile", "CarrierProfile", "FacilityProfile"]
    key: dict[str, str]
    sample_size: int
    date_from: date | None
    date_to: date | None
    source_records: list[str]
    calculated_at: AwareDatetime
    facts: dict
    rates: list[RateHistorySummary] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=lambda: [
        "Historical internal evidence, not a current market rate or pricing commitment",
        "No reliability, seasonal or SOP inference without supporting evidence"])


class ObservedPattern(Model):
    id: str
    description: str
    customer: str
    source_records: list[str]
    sample_size: int
    date_from: date | None = None
    date_to: date | None = None


class ProposedCustomerRule(ObservedPattern):
    status: Literal["PROPOSED"] = "PROPOSED"


class ApprovedCustomerRule(ObservedPattern):
    status: Literal["APPROVED"] = "APPROVED"
    approved_by: str
    approved_at: AwareDatetime
