import hashlib
import json
from datetime import datetime, timedelta

from pydantic import AwareDatetime, Field

from app.core.config import Settings
from app.core.risk import classify
from app.models.domain import AuditEvent, Model, Shipment, utcnow
from integrations.carrierview.adapter import CarrierViewAdapter
from integrations.carrierview.errors import ContractMismatch
from integrations.carrierview.mapping import IdentityExpectation, to_shipment, verify_load_identity


class ReadPlan(Model):
    expected_user_id: str
    expected_company_id: str
    identity: IdentityExpectation
    canonical: Shipment
    include_history: bool = False
    history_max_records: int = Field(default=25, ge=1, le=100)


class UiReconciliation(Model):
    candidate_hash: str
    reviewed_by: str = Field(min_length=1)
    reviewed_at: AwareDatetime
    identity_matches: bool
    tracking_values_match: bool


def candidate_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def stage_readonly_poc(adapter: CarrierViewAdapter, plan: ReadPlan, store) -> dict:
    """Exactly the bounded read sequence authorized for after owner token confirmation.

    Stages private evidence only. No POC import or LIVE_VALIDATED claim until UI reconciliation.
    """
    if plan.canonical.demo:
        raise ValueError("Read plan must contain the known real shipment, not a demo template")
    if plan.canonical.tenant_id != adapter.config.tenant_id:
        raise PermissionError("Read plan tenant mismatch")
    profile = await adapter.get_profile()
    profile_user = profile.data.user_id if profile.data.user_id is not None else profile.data.id
    if str(profile_user) != plan.expected_user_id or str(profile.data.company_id) != plan.expected_company_id:
        raise ContractMismatch("account_identity_mismatch")
    active = await adapter.search_loads()
    matches = [load for load in active.data if str(load.load_id) == plan.identity.booking_load_id]
    if len(matches) != 1:
        raise ContractMismatch("active_load_identity_ambiguous")
    verify_load_identity(matches[0], plan.identity)
    load = await adapter.get_load(plan.identity.provider_id)
    verify_load_identity(load.data, plan.identity)
    position = await adapter.get_last_position(plan.identity.provider_id)
    history = await adapter.get_positions_history(plan.identity.provider_id, plan.history_max_records) if (
        plan.include_history) else None
    shipment = to_shipment(load.data, plan.canonical, plan.identity, observed_at=load.received_at,
        credential_class=adapter.config.credential_class, last_position=position.data, position_was_read=True)
    shipment.tracking.provider_metadata["last_position_read_at"] = position.received_at.isoformat()
    shipment.risk, shipment.risk_explanation, shipment.next_action = classify(shipment, utcnow(), Settings())
    candidate = {
        "shipment": shipment.model_dump(mode="json"), "expected_user_id": plan.expected_user_id,
        "expected_company_id": plan.expected_company_id, "staged_at": utcnow().isoformat(),
        "credential_class": adapter.config.credential_class.value, "fixture": adapter.fixture_mode,
        "history": [p.model_dump(exclude_unset=True) for p in history.data] if history else None,
        "ui_reconciled": False, "live_validated": False,
    }
    digest = candidate_hash(candidate)
    with store.transaction():
        store.put(adapter.config.tenant_id, "poc_candidate", "001", {"hash": digest, "candidate": candidate})
        store.audit(AuditEvent(tenant_id=adapter.config.tenant_id, actor_id="owner-readonly-probe",
            source="carrierview", event="POC_CANDIDATE_STAGED",
            explanation="Bounded reads staged privately; awaiting owner UI reconciliation",
            credential_class=adapter.config.credential_class, verified=False,
            facts={"fixture": adapter.fixture_mode, "read_count": 5 if plan.include_history else 4}))
    return {"status": "AWAITING_UI_RECONCILIATION", "candidate_hash": digest,
            "credential_class": adapter.config.credential_class.value, "live_validated": False}


def import_reconciled_poc(store, tenant: str, confirmation: UiReconciliation):
    with store.transaction():
        staged = store.get(tenant, "poc_candidate", "001")
        value = staged["candidate"]
        if confirmation.candidate_hash != staged["hash"] or candidate_hash(value) != staged["hash"]:
            raise ValueError("Candidate changed; repeat UI reconciliation")
        if value["fixture"]:
            raise PermissionError("Synthetic fixture evidence cannot be imported as LIVE POC #001")
        if not confirmation.identity_matches or not confirmation.tracking_values_match:
            raise PermissionError("Both identity and tracking UI reconciliation must pass")
        staged_at = datetime.fromisoformat(value["staged_at"])
        now = utcnow()
        if not staged_at <= confirmation.reviewed_at <= now or now - staged_at > timedelta(minutes=15):
            raise ValueError("UI reconciliation must follow a recent read (within 15 minutes)")
        shipment = Shipment.model_validate(value["shipment"])
        if shipment.tenant_id != tenant or shipment.demo:
            raise PermissionError("Candidate tenant/demo mismatch")
        store.put(tenant, "shipment", shipment.id, shipment)
        store.put(tenant, "carrierview_load_binding", shipment.carrierview_load_id, {"shipment_id": shipment.id})
        store.put(tenant, "live_poc", "001", {
            "shipment_id": shipment.id, "live_validated": True, "credential_class": value["credential_class"],
            "verified_capabilities": ["profile_read", "active_load_search", "exact_load_read", "last_position_read"],
            "ui_reconciliation": confirmation.model_dump(mode="json"),
        })
        store.audit(AuditEvent(tenant_id=tenant, shipment_id=shipment.id, actor_id=confirmation.reviewed_by,
            source="carrierview", event="LIVE_POC_001_IMPORTED",
            explanation="Owner reconciled identity and tracking against CarrierView UI",
            credential_class=value["credential_class"], verified=True))
        return shipment


def live_projection(store, tenant):
    try:
        record = store.get(tenant, "live_poc", "001")
    except KeyError:
        return {"imported": False, "live_validated": False, "shipment": None}
    shipment = Shipment.model_validate(store.get(tenant, "shipment", record["shipment_id"]))
    if record.get("mode") == "historical":
        from app.services.historical_import import historical_projection
        return historical_projection(shipment, record)
    tracking, metadata = shipment.tracking, shipment.tracking.provider_metadata
    risk, explanation, _ = classify(shipment, utcnow(), Settings())
    return {
        "imported": True, "live_validated": record["live_validated"],
        "shipment": {
            "badge": "LIVE", "booking_load_id": shipment.booking_load_id,
            "provider_id": shipment.carrierview_load_id, "status": shipment.status,
            "tracking_status": tracking.status, "app_status": metadata.get("app_status"),
            "last_position_at": tracking.last_position_at.isoformat() if tracking.last_position_at else None,
            "current_city_state": tracking.location, "eta": tracking.eta.isoformat() if tracking.eta else None,
            "time_left_sec": metadata.get("time_left_sec"), "distance_left_meters": metadata.get("distance_left_meters"),
            "driver_is_late": metadata.get("driver_is_late"),
            "delivery_arrived": metadata.get("delivery_arrived"), "delivery_departed": metadata.get("delivery_departed"),
            "stops": metadata.get("locations"), "risk": risk, "risk_explanation": explanation,
            "last_sync_at": metadata.get("last_sync_at"), "credential_class": metadata.get("credential_class"),
        },
    }
