from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


def utcnow():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Status(StrEnum):
    TENDER_RECEIVED = "TENDER_RECEIVED"
    LOAD_CREATED = "LOAD_CREATED"
    READY_TO_COVER = "READY_TO_COVER"
    CARRIER_SELECTED = "CARRIER_SELECTED"
    CARRIER_ONBOARDING = "CARRIER_ONBOARDING"
    CARRIER_APPROVED = "CARRIER_APPROVED"
    DRIVER_INFO_REQUIRED = "DRIVER_INFO_REQUIRED"
    TRACKING_PENDING = "TRACKING_PENDING"
    TRACKING_ACTIVE = "TRACKING_ACTIVE"
    RC_PENDING = "RC_PENDING"
    RC_SENT = "RC_SENT"
    RC_SIGNED = "RC_SIGNED"
    EN_ROUTE_PICKUP = "EN_ROUTE_PICKUP"
    CHECKED_IN_PICKUP = "CHECKED_IN_PICKUP"
    LOADED = "LOADED"
    IN_TRANSIT = "IN_TRANSIT"
    EN_ROUTE_DELIVERY = "EN_ROUTE_DELIVERY"
    CHECKED_IN_DELIVERY = "CHECKED_IN_DELIVERY"
    DELIVERED = "DELIVERED"
    POD_PENDING = "POD_PENDING"
    POD_RECEIVED = "POD_RECEIVED"
    BILLING_READY = "BILLING_READY"
    CLOSED = "CLOSED"
    EXCEPTION = "EXCEPTION"


class Risk(StrEnum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    AT_RISK = "AT_RISK"
    EXCEPTION = "EXCEPTION"


class Role(StrEnum):
    OWNER = "OWNER"
    OPERATIONS_USER = "OPERATIONS_USER"
    CUSTOMER = "CUSTOMER"
    CARRIER_DISPATCHER = "CARRIER_DISPATCHER"
    DRIVER = "DRIVER"
    SYSTEM = "SYSTEM"


class ActionPolicy(StrEnum):
    ALLOW = "ALLOW"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    FORBIDDEN = "FORBIDDEN"


class Customer(Model):
    id: str
    name: str


class Carrier(Model):
    id: str
    name: str
    mc: str | None = None
    dot: str | None = None
    approved: bool = False
    setup_complete: bool = False


class Driver(Model):
    name: str
    phone: str
    truck: str | None = None
    trailer: str | None = None


class Dispatcher(Model):
    name: str
    phone: str | None = None
    email: str | None = None


class Stop(Model):
    kind: Literal["pickup", "delivery"]
    location: str
    appointment: AwareDatetime
    timezone: str = "America/Chicago"
    checked_in_at: AwareDatetime | None = None
    departed_at: AwareDatetime | None = None


class TrackingState(Model):
    status: Literal["UNKNOWN", "PENDING", "ACTIVE", "INACTIVE", "COMPLETE"] = "UNKNOWN"
    requested: bool | None = None
    accepted: bool | None = None
    last_position_at: AwareDatetime | None = None
    location: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    eta: AwareDatetime | None = None
    share_link: str | None = None
    source: str = "unknown"
    verified_at: AwareDatetime | None = None
    provider_metadata: dict = Field(default_factory=dict)


class TrackingEvent(Model):
    id: str = Field(default_factory=uid)
    timestamp: AwareDatetime
    kind: str
    state: TrackingState


class Document(Model):
    id: str = Field(default_factory=uid)
    kind: Literal["BOL", "POD", "SIGNED_RC", "PHOTO", "OTHER"]
    source: str
    received_at: AwareDatetime = Field(default_factory=utcnow)
    verified: bool = False
    storage_ref: str | None = None


class Communication(Model):
    id: str = Field(default_factory=uid)
    channel: Literal["EMAIL", "SMS", "DASHBOARD"]
    direction: Literal["INBOUND", "OUTBOUND", "DRAFT"]
    intent: str = "UNKNOWN"
    summary: str
    timestamp: AwareDatetime = Field(default_factory=utcnow)
    source: str
    verified: bool = False


class OperationalException(Model):
    id: str = Field(default_factory=uid)
    reason: str
    opened_at: AwareDatetime = Field(default_factory=utcnow)
    resolved: bool = False


class Shipment(Model):
    id: str
    tenant_id: str
    demo: bool = True
    version: int = 0
    ascend_load_id: str | None = None
    carrierview_load_id: str | None = None
    booking_load_id: str | None = None
    provider_metadata: dict = Field(default_factory=dict)
    customer_reference: str | None = None
    customer: Customer | None = None
    carrier: Carrier | None = None
    driver: Driver | None = None
    dispatcher: Dispatcher | None = None
    origin: Stop
    destination: Stop
    status: Status = Status.TENDER_RECEIVED
    exception_previous_status: Status | None = None
    tracking: TrackingState = Field(default_factory=TrackingState)
    risk: Risk = Risk.WARNING
    risk_explanation: str = "Not evaluated"
    required_documents: list[str] = Field(default_factory=lambda: ["BOL", "POD", "SIGNED_RC"])
    documents: list[Document] = Field(default_factory=list)
    communications: list[Communication] = Field(default_factory=list)
    tracking_timeline: list[TrackingEvent] = Field(default_factory=list)
    exceptions: list[OperationalException] = Field(default_factory=list)
    last_carrier_communication: AwareDatetime | None = None
    last_driver_communication: AwareDatetime | None = None
    last_customer_communication: AwareDatetime | None = None
    last_action: str = "Demo seeded"
    next_action: str = "Evaluate tracking"
    next_action_at: AwareDatetime | None = None
    workflow: str = "in_transit_to_billing"
    paused: bool = False
    human_takeover: bool = False
    ascend_state: str | None = None


class AuthorizedIdentity(Model):
    id: str
    tenant_id: str
    role: Role
    shipment_ids: list[str] = Field(default_factory=list)
    customer_id: str | None = None


class ExternalEvent(Model):
    id: str = Field(default_factory=uid)
    tenant_id: str
    shipment_id: str
    source: str
    kind: Literal["REVIEW", "TRANSITION"]
    occurred_at: AwareDatetime = Field(default_factory=utcnow)
    expected_version: int | None = None
    target_status: Status | None = None


class AuditEvent(Model):
    id: str = Field(default_factory=uid)
    tenant_id: str
    shipment_id: str | None = None
    timestamp: AwareDatetime = Field(default_factory=utcnow)
    actor_id: str
    source: str
    event: str
    explanation: str
    facts: dict = Field(default_factory=dict)
    action: str | None = None
    policy: ActionPolicy | None = None
    approval_status: str | None = None
    execution_status: str | None = None
    executor: str | None = None
    model: str | None = None
    duration_ms: float | None = None
    verified: bool = False
    error_code: str | None = None
    retry_count: int = 0
    credential_class: Literal["agent", "tenant"] | None = None
    external_action_id: str | None = None


class ApprovalRequest(Model):
    id: str = Field(default_factory=uid)
    tenant_id: str
    shipment_id: str
    action: str
    explanation: str
    expected_version: int
    expected_risk: Risk | None = None
    status: Literal["PENDING", "APPROVED", "REJECTED", "EXPIRED"] = "PENDING"
    created_at: AwareDatetime = Field(default_factory=utcnow)
    expires_at: AwareDatetime
    decided_by: str | None = None
    decided_at: AwareDatetime | None = None


class Task(Model):
    id: str = Field(default_factory=uid)
    tenant_id: str
    shipment_id: str
    kind: Literal["REVIEW"] = "REVIEW"
    due_at: AwareDatetime
    status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"] = "QUEUED"
    attempts: int = 0
    max_attempts: int = 3
    last_error: str | None = None


class AgentState(Model):
    name: str = "Avery"
    company: str = "Booking Logistics"
    role: str = "AI Operations Assistant"
    status: Literal["ACTIVE", "PAUSED", "ERROR"] = "ACTIVE"
    current_task: str = "Scheduled demo shipment reviews"
    last_heartbeat: AwareDatetime = Field(default_factory=utcnow)


class SystemConnection(Model):
    name: str
    status: Literal["NOT_CONFIGURED", "DISABLED", "CONNECTED", "ERROR"] = "NOT_CONFIGURED"
    detail: str
    implemented: bool = False
    tested: bool = False
    live_validated: bool = False


class ExecutionResult(Model):
    job_id: str
    success: bool
    verified: bool
    executor: str
    duration_ms: float
    evidence: dict = Field(default_factory=dict)
    error_code: str | None = None


class ModelInvocation(Model):
    id: str = Field(default_factory=uid)
    tenant_id: str
    provider: str
    model: str
    purpose: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    duration_ms: float | None = None
    escalation_reason: str | None = None


class BrowserExecution(Model):
    job_id: str = Field(default_factory=uid)
    tenant_id: str
    shipment_id: str
    external_load_id: str
    action: str
    expected_state: str
    intended_state: str
    authorization_id: str
    deadline: AwareDatetime
