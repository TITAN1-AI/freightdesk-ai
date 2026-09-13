"""Offline, owner-reconciled historical import; no provider I/O or scheduler enqueue."""
from datetime import datetime

from app.models.domain import AuditEvent, Risk, Shipment, Status, Stop, TrackingState, utcnow
from app.services.carrierview_historical import exact_record, reconcile_list_detail
from app.services.carrierview_historical_report import historical_report
from app.services.carrierview_poc import candidate_hash

PROVEN = {
    "Tenant authentication and company profile read": True,
    "Past-load discovery": True,
    "Exact shipment read and identity reconciliation": True,
    "Last-position retrieval (raw timestamp units unverified)": True,
    "Position-history retrieval (first page only)": True,
    "Historical stop timeline and owner UI reconciliation": True,
    "Canonical historical import": True,
    "Protected historical dashboard display": True,
    "Real-time monitoring": False,
    "Webhook processing": False,
    "Tracking creation/initiation": False,
    "SMS": False,
    "Chat": False,
    "Live autonomous execution": False,
    "POD": False,
    "Signed RC": False,
    "Billing readiness": False,
}


def build_historical(bundle, confirmation):
    if bundle.get("fixture") is not False:
        raise PermissionError("Fixture evidence cannot be imported as production")
    if confirmation["evidence_hash"] != candidate_hash(bundle):
        raise PermissionError("Historical evidence changed after owner reconciliation")
    if confirmation.get("approved") is not True:
        raise PermissionError("Owner import approval required")
    candidate = bundle["candidate"]
    provider, booking = confirmation["provider_id"], confirmation["booking_reference"]
    if str(candidate.get("id")) != provider or str(candidate.get("load_id")) != booking:
        raise PermissionError("Owner selection does not match historical evidence")
    detail = exact_record(bundle["detail"], provider, booking)
    if not all(v is True for v in reconcile_list_detail(candidate, detail).values()):
        raise PermissionError("Historical identity reconciliation incomplete")
    report = historical_report(candidate, detail, bundle["position"], bundle["history"])
    # Owner confirmed UI times to the minute. Preserve original source seconds in canonical facts.
    for row in report["stops"]:
        expected = confirmation["stops"][row["kind"]]
        for field in ("appointment_start", "appointment_end", "arrived_at", "departed_at"):
            if datetime.fromisoformat(row[field]).isoformat(timespec="minutes") != expected[field]:
                raise PermissionError("Owner UI stop/time comparison failed")
    if detail.get("delivery_arrived") is not True or detail.get("delivery_departed") is not True:
        raise PermissionError("Historical delivery facts do not match confirmed completion")
    observed = datetime.fromisoformat(bundle["observed_at"])
    stops = []
    for row in report["stops"]:
        source = next(s for s in detail["locations"] if s["type"] == row["kind"])
        stops.append(Stop(kind="pickup" if row["kind"] == "pickup" else "delivery",
            location=source["address"], appointment=datetime.fromisoformat(row["appointment_start"]),
            timezone=row["timezone"], checked_in_at=datetime.fromisoformat(row["arrived_at"]),
            departed_at=datetime.fromisoformat(row["departed_at"])))
    tracking = TrackingState(source="carrierview", verified_at=observed,
        status="UNKNOWN", accepted=None, requested=None,
        provider_metadata={"raw_load": detail, "raw_last_position": bundle["position"],
            "raw_positions_history": bundle["history"], "credential_class": "tenant",
            "app_status": (detail.get("track_driver") or {}).get("app_status"),
            "time_left_sec": detail.get("time_left_sec"), "distance_left_meters": detail.get("distance_left_meters"),
            "driver_is_late": detail.get("driver_is_late"), "delivery_arrived": detail.get("delivery_arrived"),
            "delivery_departed": detail.get("delivery_departed"), "last_sync_at": bundle["observed_at"]})
    # Customer, driver name, documents and acceptance remain unknown; do not invent placeholders.
    shipment = Shipment(id="live-poc-001", tenant_id="booking-logistics", demo=False,
        booking_load_id=booking, carrierview_load_id=provider, customer=None,
        origin=stops[0], destination=stops[1], status=Status.DELIVERED, tracking=tracking,
        workflow="historical_production_replay", paused=True, human_takeover=True,
        risk=Risk.WARNING, risk_explanation="Historical arrival windows met; document and billing readiness unverified",
        next_action="Historical replay only; no automated operational action",
        last_action="Owner-reconciled historical CarrierView import",
        provider_metadata={"carrierview": {"provider_id": provider, "booking_load_id": booking,
            "tracking_number_url": detail.get("tracking_number_url"), "client_url": detail.get("client_url"),
            "credential_class": "tenant", "source_evidence_hash": confirmation["evidence_hash"]},
            "historical_replay": {"report": report, "owner_reconciliation": confirmation,
                "canonical_status_source": "FreightDesk mapping of provider delivery flags plus owner reconciliation",
                "risk_source": "FreightDesk-derived historical assessment; not a CarrierView risk classification",
                "unknown_facts": ["customer", "driver_name", "tracking_acceptance", "POD", "SIGNED_RC", "billing_readiness"]}})
    return shipment


def import_historical(store, bundle, confirmation):
    shipment = build_historical(bundle, confirmation)
    tenant = shipment.tenant_id
    digest = confirmation["evidence_hash"]
    with store.transaction():
        existing = store.all(tenant, "live_poc")
        if existing:
            if len(existing) == 1 and existing[0].get("evidence_hash") == digest:
                return {"status": "ALREADY_IMPORTED", "shipment_id": shipment.id}
            raise PermissionError("LIVE POC already exists with different evidence")
        store.put(tenant, "shipment", shipment.id, shipment)
        store.put(tenant, "carrierview_load_binding", shipment.carrierview_load_id, {"shipment_id": shipment.id})
        store.put(tenant, "live_poc", "001", {"shipment_id": shipment.id,
            "title": "LIVE POC #001 — Historical Production Replay", "mode": "historical",
            "live_validated": True, "credential_class": "tenant", "capability_matrix": PROVEN,
            "evidence_hash": digest, "ui_reconciliation": confirmation, "imported_at": utcnow().isoformat()})
        store.audit(AuditEvent(tenant_id=tenant, shipment_id=shipment.id, actor_id="owner",
            source="carrierview", event="HISTORICAL_POC_IMPORTED", credential_class="tenant", verified=True,
            explanation="Owner approved reconciled historical evidence; no operational work scheduled",
            facts={"evidence_hash": digest, "historical_only": True, "proven_capabilities": list(
                key for key, value in PROVEN.items() if value)}))
    return {"status": "IMPORTED", "shipment_id": shipment.id, "capability_matrix": PROVEN}


def historical_projection(shipment, record):
    report = shipment.provider_metadata["historical_replay"]["report"]
    metadata = shipment.tracking.provider_metadata
    return {"imported": True, "live_validated": True, "title": record["title"],
        "capability_matrix": record["capability_matrix"], "shipment": {
            "historical": True, "title": record["title"], "booking_load_id": shipment.booking_load_id,
            "provider_id": shipment.carrierview_load_id, "credential_class": "tenant",
            "provider_facts": {"app_status": report["app_status"],
                "delivery_arrived": report["delivery_arrived"], "delivery_departed": report["delivery_departed"],
                "time_left_sec": report["time_remaining_seconds"],
                "distance_left_meters": report["distance_remaining_meters"],
                "last_position_returned": report["last_position_returned"],
                "history_records_received": report["history_records_received"],
                "history_pagination": report["history_pagination"], "last_sync_at": metadata["last_sync_at"]},
            "stops": report["stops"],
            "derived": {"canonical_status": shipment.status, "arrival_assessment": report["arrival_assessment"],
                "risk": shipment.risk, "risk_explanation": shipment.risk_explanation,
                "billing_readiness": "UNVERIFIED", "numeric_timestamp_units": "UNVERIFIED"},
            "capability_matrix": record["capability_matrix"], "owner_reconciled": True,
            "automated_actions_enabled": False}}
