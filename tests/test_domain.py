from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.risk import classify
from app.core.state_machine import LIFECYCLE, TrackingGate, rc_gate_errors, transition
from app.models.domain import (
    AuthorizedIdentity, Document, OperationalException, Risk, Role, Status, TrackingState, utcnow,
)
from app.security.authorization import authorize
from app.services.demo import demo_shipments
from model_providers.interfaces.provider import route


def sample():
    return demo_shipments("booking-logistics")[0]


def test_full_lifecycle_and_required_document_gates():
    s = sample()
    s.status = Status.TENDER_RECEIVED
    s.documents.append(Document(kind="POD", source="test", verified=True))
    for status in LIFECYCLE[1:]:
        s = transition(s, status)
    assert s.status == Status.CLOSED


@pytest.mark.parametrize("target", [Status.BILLING_READY, Status.RC_SENT, Status.CLOSED, Status.IN_TRANSIT])
def test_invalid_transition_rejected(target):
    s = sample()
    with pytest.raises(ValueError):
        transition(s, target)


def test_tracking_gate_rechecked_before_rc():
    s = sample()
    s.status = Status.RC_PENDING
    s.tracking.accepted = False
    with pytest.raises(ValueError, match="Tracking not active"):
        transition(s, Status.RC_SENT)
    assert rc_gate_errors(s, TrackingGate(tracking_active=False)) == []


@pytest.mark.parametrize("field", ["carrier", "driver", "tracking"])
def test_tracking_prerequisites_fail_closed(field):
    s = sample()
    if field == "tracking":
        s.tracking.requested = False
    else:
        setattr(s, field, None)
    assert rc_gate_errors(s)


def test_billing_requires_verified_documents_and_resolved_exceptions():
    s = sample()
    s.status = Status.POD_PENDING
    s.documents.append(Document(kind="POD", source="test"))
    with pytest.raises(ValueError, match="Verified POD"):
        transition(s, Status.POD_RECEIVED)
    s.documents[-1].verified = True
    s = transition(s, Status.POD_RECEIVED)
    s.exceptions.append(OperationalException(reason="Delivery discrepancy"))
    with pytest.raises(ValueError, match="Billing gate"):
        transition(s, Status.BILLING_READY)
    s.exceptions[0].resolved = True
    assert transition(s, Status.BILLING_READY).status == Status.BILLING_READY


def test_exception_recovery_is_constrained():
    s = transition(sample(), Status.EXCEPTION)
    with pytest.raises(ValueError):
        transition(s, Status.BILLING_READY)
    assert transition(s, Status.IN_TRANSIT).exception_previous_status is None


def test_naive_timestamps_rejected():
    with pytest.raises(ValidationError):
        TrackingState(last_position_at="2026-09-07T12:00:00")


@pytest.mark.parametrize("age,risk", [(6, Risk.HEALTHY), (30, Risk.WARNING), (60, Risk.AT_RISK)])
def test_tracking_age_boundaries(age, risk):
    s, now = sample(), utcnow()
    s.tracking.last_position_at = now - timedelta(minutes=age)
    result = classify(s, now, Settings())
    assert result[0] == risk
    if risk == Risk.HEALTHY:
        assert result[2] == "No driver contact required"


@pytest.mark.parametrize("case", ["future", "missing", "unverified", "inactive", "expired_eta"])
def test_uncertain_tracking_never_healthy(case):
    s, now = sample(), utcnow()
    if case == "future":
        s.tracking.last_position_at = now + timedelta(minutes=1)
    elif case == "missing":
        s.tracking.last_position_at = None
    elif case == "unverified":
        s.tracking.verified_at = None
    elif case == "inactive":
        s.tracking.accepted = False
    else:
        s.tracking.eta = now - timedelta(minutes=1)
    assert classify(s, now, Settings())[0] == Risk.WARNING


def test_late_eta_is_at_risk_even_when_gps_fresh():
    s = sample()
    s.tracking.eta = s.destination.appointment + timedelta(minutes=22)
    risk, explanation, _ = classify(s, utcnow(), Settings())
    assert risk == Risk.AT_RISK
    assert "22 minutes" in explanation


def test_missing_bol_prevents_healthy_classification():
    s = sample()
    s.documents = [d for d in s.documents if d.kind != "BOL"]
    risk, explanation, _ = classify(s, utcnow(), Settings())
    assert risk == Risk.WARNING
    assert "BOL" in explanation


def test_delivered_load_does_not_request_tracking_followup():
    s = sample()
    s.status = Status.POD_PENDING
    s.tracking = TrackingState()
    risk, _, action = classify(s, utcnow(), Settings())
    assert risk == Risk.WARNING
    assert action == "Collect missing documents"


def test_roles_and_tenant_boundaries():
    s = sample()
    driver = AuthorizedIdentity(id="driver", tenant_id=s.tenant_id, role=Role.DRIVER, shipment_ids=[s.id])
    authorize(driver, s.tenant_id, "read", s)
    with pytest.raises(PermissionError):
        authorize(driver, s.tenant_id, "pause", s)
    with pytest.raises(PermissionError):
        authorize(driver, "different-tenant", "read", s)
    driver.shipment_ids = []
    with pytest.raises(PermissionError):
        authorize(driver, s.tenant_id, "read", s)


def test_customer_cannot_see_other_customer():
    s = sample()
    customer = AuthorizedIdentity(id="customer", tenant_id=s.tenant_id, role=Role.CUSTOMER, customer_id="other")
    with pytest.raises(PermissionError):
        authorize(customer, s.tenant_id, "read", s)


def test_model_routing_avoids_llm_for_deterministic_work():
    assert route("risk", "small", "balanced", "strong") is None
    assert route("ambiguous", "small", "balanced", "strong") == "strong"


@pytest.mark.parametrize("kwargs", [{"tenant": "../escape"}, {"mode": "live"}, {"mode": "dry_run"}])
def test_unsupported_configuration_fails_closed(kwargs):
    with pytest.raises(ValueError):
        Settings(**kwargs)
