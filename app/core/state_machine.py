from dataclasses import dataclass

from app.models.domain import Shipment, Status

LIFECYCLE = [s for s in Status if s != Status.EXCEPTION]
TRANSITIONS = {s: {LIFECYCLE[i + 1]} for i, s in enumerate(LIFECYCLE[:-1])}
TRANSITIONS[Status.CARRIER_SELECTED].add(Status.CARRIER_APPROVED)


@dataclass(frozen=True)
class TrackingGate:
    carrier_approved: bool = True
    setup_complete: bool = True
    driver_complete: bool = True
    tracking_requested: bool = True
    tracking_active: bool = True


def rc_gate_errors(shipment: Shipment, gate: TrackingGate = TrackingGate()) -> list[str]:
    checks = [
        (gate.carrier_approved, shipment.carrier and shipment.carrier.approved, "Carrier not approved"),
        (gate.setup_complete, shipment.carrier and shipment.carrier.setup_complete, "Carrier setup incomplete"),
        (gate.driver_complete, shipment.driver and all([
            shipment.driver.name, shipment.driver.phone, shipment.driver.truck, shipment.driver.trailer]),
         "Driver information incomplete"),
        (gate.tracking_requested, shipment.tracking.requested, "Tracking not requested"),
        (gate.tracking_active, shipment.tracking.accepted and shipment.tracking.status == "ACTIVE",
         "Tracking not active and accepted"),
    ]
    return [message for required, satisfied, message in checks if required and not satisfied]


def transition(shipment: Shipment, target: Status, gate: TrackingGate = TrackingGate()) -> Shipment:
    current = shipment.status
    if current == target:
        raise ValueError("Shipment is already in requested state")
    if target == Status.EXCEPTION:
        if current == Status.CLOSED:
            raise ValueError("Closed shipments cannot enter exception")
        return shipment.model_copy(update={"status": target, "exception_previous_status": current})
    if current == Status.EXCEPTION:
        if target != shipment.exception_previous_status or any(not e.resolved for e in shipment.exceptions):
            raise ValueError("Resolve exceptions and return to the previous state first")
        return shipment.model_copy(update={"status": target, "exception_previous_status": None})
    if target not in TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid transition: {current} → {target}")
    if target == Status.CARRIER_APPROVED and not (
        shipment.carrier and shipment.carrier.approved and shipment.carrier.setup_complete
    ):
        raise ValueError("Verified carrier approval and setup are required")
    if target == Status.TRACKING_ACTIVE and not (
        shipment.tracking.requested and shipment.tracking.accepted and shipment.tracking.status == "ACTIVE"
    ):
        raise ValueError("Tracking must be requested, accepted and active")
    if target in {Status.RC_PENDING, Status.RC_SENT}:
        errors = rc_gate_errors(shipment, gate)
        if errors:
            raise ValueError("; ".join(errors))
    verified = {d.kind for d in shipment.documents if d.verified}
    if target == Status.RC_SIGNED and "SIGNED_RC" not in verified:
        raise ValueError("Verified signed RC required")
    if target == Status.POD_RECEIVED and "POD" not in verified:
        raise ValueError("Verified POD required")
    if target == Status.BILLING_READY:
        missing = set(shipment.required_documents) - verified
        if missing or any(not e.resolved for e in shipment.exceptions):
            raise ValueError("Billing gate: missing verified documents or unresolved exceptions")
    return shipment.model_copy(update={"status": target})
