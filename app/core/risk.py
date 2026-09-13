from datetime import datetime

from app.core.config import Settings
from app.models.domain import Risk, Shipment, Status


def classify(shipment: Shipment, now: datetime, settings: Settings) -> tuple[Risk, str, str]:
    if shipment.status == Status.EXCEPTION or any(not e.resolved for e in shipment.exceptions):
        return Risk.EXCEPTION, "Unresolved operational exception", "Human review required"
    if (shipment.tracking.source == "carrierview"
            and shipment.tracking.provider_metadata.get("driver_is_late") is True
            and shipment.status not in {Status.DELIVERED, Status.POD_PENDING, Status.POD_RECEIVED,
                                        Status.BILLING_READY, Status.CLOSED}):
        return Risk.AT_RISK, "CarrierView reports driver_is_late = true", "Verify appointment risk with broker"
    if shipment.status in {Status.DELIVERED, Status.POD_PENDING, Status.POD_RECEIVED,
                           Status.BILLING_READY, Status.CLOSED}:
        missing = set(shipment.required_documents) - {d.kind for d in shipment.documents if d.verified}
        if shipment.status != Status.CLOSED and missing:
            return Risk.WARNING, "Missing verified documents: " + ", ".join(sorted(missing)), "Collect missing documents"
        return Risk.HEALTHY, "Delivery document requirements satisfied", "Review billing readiness"
    tracking = shipment.tracking
    if not tracking.verified_at or tracking.source == "unknown":
        return Risk.WARNING, "Tracking facts have no verification provenance", "Reconcile tracking source"
    if tracking.verified_at > now or (tracking.last_position_at and tracking.last_position_at > now):
        return Risk.WARNING, "Tracking timestamp is in the future", "Verify source clock"
    if not tracking.accepted or tracking.status != "ACTIVE":
        return Risk.WARNING, "Tracking is not active and accepted", "Review tracking activation / follow-up"
    if not tracking.last_position_at:
        return Risk.WARNING, "No position timestamp available", "Reconcile tracking source"
    age = (now - tracking.last_position_at).total_seconds() / 60
    appointment = (shipment.destination.appointment if shipment.status in {
        Status.IN_TRANSIT, Status.EN_ROUTE_DELIVERY, Status.CHECKED_IN_DELIVERY
    } else shipment.origin.appointment)
    if tracking.eta and tracking.eta > appointment:
        late = round((tracking.eta - appointment).total_seconds() / 60)
        return Risk.AT_RISK, f"ETA exceeds appointment by {late} minutes", "Broker review of appointment risk"
    if age >= settings.escalation_minutes:
        return Risk.AT_RISK, f"Tracking stale for {int(age)} minutes", "Escalate stale tracking"
    if age >= settings.stale_minutes:
        return Risk.WARNING, f"Tracking stale for {int(age)} minutes", "Reconcile before contacting driver"
    if not tracking.eta or tracking.eta < now:
        return Risk.WARNING, "ETA is missing or expired", "Request updated ETA from tracking source"
    if shipment.status in {Status.LOADED, Status.IN_TRANSIT, Status.EN_ROUTE_DELIVERY,
                           Status.CHECKED_IN_DELIVERY}:
        missing = (set(shipment.required_documents) - {"POD"}) - {
            d.kind for d in shipment.documents if d.verified
        }
        if missing:
            return Risk.WARNING, "Missing operational documents: " + ", ".join(sorted(missing)), "Collect missing documents"
    margin = round((appointment - tracking.eta).total_seconds() / 60)
    return Risk.HEALTHY, f"Tracking updated {int(age)} minutes ago; ETA {margin} minutes before appointment", "No driver contact required"
