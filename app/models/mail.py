from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field

from app.models.domain import ExternalEvent, Model
from integrations.outlook.models import Message


class MailIntent(StrEnum):
    CUSTOMER_LOAD_TENDER = "CUSTOMER_LOAD_TENDER"
    CUSTOMER_QUOTE_REQUEST = "CUSTOMER_QUOTE_REQUEST"
    CUSTOMER_STATUS_REQUEST = "CUSTOMER_STATUS_REQUEST"
    CARRIER_BOOKING_INFO = "CARRIER_BOOKING_INFO"
    CARRIER_UPDATE = "CARRIER_UPDATE"
    DISPATCHER_UPDATE = "DISPATCHER_UPDATE"
    DRIVER_INFO = "DRIVER_INFO"
    DRIVER_UPDATE = "DRIVER_UPDATE"
    ETA_UPDATE = "ETA_UPDATE"
    TRACKING_RESPONSE = "TRACKING_RESPONSE"
    SIGNED_RATE_CONFIRMATION = "SIGNED_RATE_CONFIRMATION"
    BOL = "BOL"
    POD = "POD"
    SHIPMENT_PHOTO = "SHIPMENT_PHOTO"
    OTHER_LOAD_DOCUMENT = "OTHER_LOAD_DOCUMENT"
    CARRIER_SETUP_REQUEST = "CARRIER_SETUP_REQUEST"
    ACCESSORIAL_REQUEST = "ACCESSORIAL_REQUEST"
    EXCEPTION_REPORT = "EXCEPTION_REPORT"
    OWNER_COMMAND = "OWNER_COMMAND"
    UNKNOWN = "UNKNOWN"


class FactEvidence(Model):
    field: str
    source_message_id: str
    source_text: str = Field(max_length=500, repr=False)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    observed_at: AwareDatetime | None = None
    verification: Literal["UNVERIFIED", "VERIFIED"] = "UNVERIFIED"


class FreightFacts(Model):
    load_reference: str | None = None
    customer_reference: str | None = None
    customer: str | None = None
    carrier: str | None = None
    mc: str | None = None
    dot: str | None = None
    dispatcher_name: str | None = None
    dispatcher_email: str | None = None
    dispatcher_phone: str | None = None
    driver_name: str | None = None
    driver_phone: str | None = None
    truck_number: str | None = None
    trailer_number: str | None = None
    origin: str | None = None
    destination: str | None = None
    pickup_facility: str | None = None
    delivery_facility: str | None = None
    pickup_appointment: AwareDatetime | None = None
    delivery_appointment: AwareDatetime | None = None
    equipment: str | None = None
    weight: Decimal | None = None
    commodity: str | None = None
    current_location: str | None = None
    truck_status: Literal["EMPTY", "EN_ROUTE_PICKUP", "CHECKED_IN_PICKUP", "LOADED",
                          "IN_TRANSIT", "EN_ROUTE_DELIVERY", "CHECKED_IN_DELIVERY", "DELIVERED"] | None = None
    movement: Literal["EN_ROUTE_PICKUP", "EN_ROUTE_DELIVERY"] | None = None
    pickup_eta: AwareDatetime | None = None
    delivery_eta: AwareDatetime | None = None
    eta_text: str | None = None
    customer_rate: Decimal | None = None
    carrier_rate: Decimal | None = None
    currency: str | None = None
    evidence: list[FactEvidence] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)


class Classification(Model):
    intent: MailIntent = MailIntent.UNKNOWN
    confidence: float = Field(default=0, ge=0, le=1)
    source: Literal["rules", "model", "unavailable"] = "rules"
    review_required: bool = True


class MailExternalEvent(ExternalEvent):
    kind: Literal["MAIL_DISCOVERED"] = "MAIL_DISCOVERED"
    shipment_id: str | None = None
    source: Literal["microsoft_graph"] = "microsoft_graph"
    mailbox: str
    message: Message
    processing_state: Literal["DISCOVERED", "PROCESSED", "REVIEW_REQUIRED", "FAILED"] = "DISCOVERED"
    classification: Classification = Field(default_factory=Classification)
    extracted: FreightFacts = Field(default_factory=FreightFacts)
    match_confidence: float = 0
    action_taken: str = "NONE"
