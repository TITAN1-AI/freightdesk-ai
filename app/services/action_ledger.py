import asyncio
import hashlib
import json
from datetime import timedelta
from typing import Awaitable, Callable, Literal

from pydantic import AwareDatetime, Field

from app.models.domain import (
    ActionPolicy, AuditEvent, AuthorizedIdentity, Model, Shipment, uid, utcnow,
)
from app.security.authorization import authorize
from app.services.store import Store
from integrations.carrierview.errors import CarrierViewError

ActionState = Literal["AWAITING_APPROVAL", "QUEUED", "IN_FLIGHT", "SUCCEEDED", "FAILED", "UNCERTAIN", "BLOCKED"]
ACTION_TYPES = {
    "create_tracking_load", "edit_load", "disable_load", "send_driver_chat_message",
    "send_driver_text_message", "configure_webhooks",
}


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class ExternalAction(Model):
    id: str = Field(default_factory=uid)
    tenant_id: str
    shipment_id: str
    provider: Literal["carrierview"] = "carrierview"
    provider_load_id: str | None
    recipient: str
    action_type: str
    request_method: Literal["POST", "PATCH", "PUT"]
    request_path: str
    payload_hash: str
    payload: dict = Field(repr=False)
    credential_class: Literal["agent", "tenant"]
    created_at: AwareDatetime = Field(default_factory=utcnow)
    expected_shipment_version: int
    attempts: int = 0
    state: ActionState = "AWAITING_APPROVAL"
    last_attempt_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    provider_result: dict | None = Field(default=None, repr=False)
    approved_by: str | None = None
    approved_at: AwareDatetime | None = None
    approval_expires_at: AwareDatetime | None = None
    uncertain_result: bool = False
    reconciliation_required: bool = False


class ActionLedger:
    """Durable outbox foundation: claim once, never replay an attempted action automatically.

    Uses the same tenant-scoped Store as the canonical shipment. Production callers must
    use the authorized nonsynced store; fixture stores may contain only synthetic data.
    """

    def __init__(self, store: Store, tenant: str):
        self.store, self.tenant = store, tenant

    def get(self, action_id):
        return ExternalAction.model_validate(self.store.get(self.tenant, "external_action", action_id))

    def save(self, action):
        self.store.put(self.tenant, "external_action", action.id, action)

    def audit(self, actor, action, event, error_code=None):
        self.store.audit(AuditEvent(tenant_id=self.tenant, shipment_id=action.shipment_id,
            actor_id=actor.id, source="external_action_ledger", event=event,
            explanation="Bounded external action state recorded; payload/recipient excluded from audit",
            action=action.action_type, external_action_id=action.id, credential_class=action.credential_class,
            execution_status=action.state, error_code=error_code, retry_count=max(0, action.attempts - 1),
            facts={"attempt_count": action.attempts, "reconciliation_required": action.reconciliation_required}))

    def enqueue(self, identity: AuthorizedIdentity, shipment_id: str, *, action_id: str, recipient: str,
                action_type: str, provider_load_id: str | None, credential_class: str,
                method: str, path: str, payload: dict, policy: ActionPolicy):
        with self.store.transaction():
            shipment = Shipment.model_validate(self.store.get(self.tenant, "shipment", shipment_id))
            authorize(identity, self.tenant, "request_action", shipment)
            if action_type not in ACTION_TYPES or policy == ActionPolicy.FORBIDDEN:
                raise PermissionError("External action forbidden or unsupported")
            if shipment.paused or shipment.human_takeover:
                raise PermissionError("Shipment is paused or under human control")
            if provider_load_id is not None and shipment.carrierview_load_id != provider_load_id:
                raise PermissionError("Provider load must match the canonical shipment binding")
            if action_type == "create_tracking_load" and shipment.carrierview_load_id is not None:
                raise PermissionError("Shipment already has a CarrierView provider binding")
            if action_type in {"send_driver_chat_message", "send_driver_text_message"}:
                if not shipment.driver or recipient != shipment.driver.phone:
                    raise PermissionError("Message recipient must match the verified shipment driver")
            action = ExternalAction(id=action_id, tenant_id=self.tenant, shipment_id=shipment_id,
                provider_load_id=provider_load_id, recipient=recipient, action_type=action_type,
                request_method=method, request_path=path, payload_hash=payload_hash(payload), payload=payload,
                credential_class=credential_class, expected_shipment_version=shipment.version,
                state="QUEUED" if policy == ActionPolicy.ALLOW else "AWAITING_APPROVAL")
            try:
                previous = self.get(action_id)
            except KeyError:
                previous = None
            if previous:
                fields = ["tenant_id", "shipment_id", "recipient", "action_type", "request_method",
                          "request_path", "payload_hash", "credential_class", "provider_load_id"]
                if any(getattr(previous, f) != getattr(action, f) for f in fields):
                    raise ValueError("External action ID reused with different binding")
                return previous
            self.save(action)
            self.audit(identity, action, "EXTERNAL_ACTION_QUEUED")
            return action

    def approve(self, identity, action_id):
        with self.store.transaction():
            authorize(identity, self.tenant, "approve")
            action = self.get(action_id)
            if action.state != "AWAITING_APPROVAL" or action.attempts:
                raise ValueError("External action is not awaiting approval")
            action.approved_by, action.approved_at = identity.id, utcnow()
            action.approval_expires_at = utcnow() + timedelta(minutes=15)
            action.state = "QUEUED"
            self.save(action)
            self.audit(identity, action, "EXTERNAL_ACTION_APPROVED")
            return action

    async def dispatch(self, identity, action_id, sender: Callable[[ExternalAction], Awaitable[dict]],
                       *, current_policy: ActionPolicy, agent_paused: bool = False):
        with self.store.transaction():
            action = self.get(action_id)
            shipment = Shipment.model_validate(self.store.get(self.tenant, "shipment", action.shipment_id))
            authorize(identity, self.tenant, "request_action", shipment)
            if action.state != "QUEUED" or action.attempts != 0:
                raise PermissionError("Only an unattempted queued action can be dispatched")
            approval_valid = (action.approved_by and action.approval_expires_at
                              and action.approval_expires_at > utcnow())
            try:
                agent_paused = agent_paused or self.store.get(self.tenant, "agent", "avery")["status"] != "ACTIVE"
            except KeyError:
                raise PermissionError("Persisted agent control state required before external dispatch") from None
            if (current_policy == ActionPolicy.FORBIDDEN or
                    (current_policy == ActionPolicy.APPROVAL_REQUIRED and not approval_valid)):
                raise PermissionError("Current external action policy/approval does not permit dispatch")
            if (agent_paused or shipment.paused or shipment.human_takeover
                    or shipment.version != action.expected_shipment_version):
                raise PermissionError("Pause, takeover or changed shipment blocks dispatch")
            if payload_hash(action.payload) != action.payload_hash:
                raise PermissionError("Stored payload hash mismatch")
            if action.provider_load_id is not None and shipment.carrierview_load_id != action.provider_load_id:
                raise PermissionError("Provider load binding changed")
            if action.action_type in {"send_driver_chat_message", "send_driver_text_message"}:
                if not shipment.driver or action.recipient != shipment.driver.phone:
                    raise PermissionError("Driver recipient changed")
            now = utcnow()
            if action.action_type == "send_driver_text_message":
                recent = [ExternalAction.model_validate(row) for row in
                          self.store.all(self.tenant, "external_action")]
                count = sum(a.action_type == "send_driver_text_message" and a.last_attempt_at is not None
                            and a.last_attempt_at > now - timedelta(minutes=1) for a in recent)
                if count >= 5:
                    raise CarrierViewError("local_sms_rate_limit", retry_after_seconds=60)
            action.state, action.attempts, action.last_attempt_at = "IN_FLIGHT", 1, now
            self.save(action)
            self.audit(identity, action, "EXTERNAL_ACTION_CLAIMED")
        # Never hold a DB transaction across network I/O.
        try:
            result = await sender(action.model_copy(deep=True))
            if not isinstance(result, dict) or result.get("success") is not True:
                raise CarrierViewError("unverified_write_result", uncertain=True)
            with self.store.transaction():
                action = self.get(action_id)
                action.state, action.provider_result = "SUCCEEDED", result
                action.completed_at = utcnow()
                self.save(action)
                self.audit(identity, action, "EXTERNAL_ACTION_SUCCEEDED")
        except BaseException as error:
            # After dispatch begins any unexpected/cancelled outcome is uncertain. No auto retry.
            uncertain = not isinstance(error, (CarrierViewError, PermissionError)) or (
                isinstance(error, CarrierViewError) and error.uncertain)
            code = error.code if isinstance(error, CarrierViewError) else (
                "dispatch_forbidden" if isinstance(error, PermissionError) else "unexpected_dispatch_outcome")
            with self.store.transaction():
                action = self.get(action_id)
                action.state = "UNCERTAIN" if uncertain else "FAILED"
                action.uncertain_result = action.reconciliation_required = uncertain
                action.completed_at = None if uncertain else utcnow()
                action.provider_result = error.safe_result() if isinstance(error, CarrierViewError) else {"error_code": code}
                self.save(action)
                self.audit(identity, action, "EXTERNAL_ACTION_" + action.state, code)
            if isinstance(error, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)):
                raise
        return action

    def recover_abandoned(self, identity, before):
        """Explicit startup reconciliation: abandoned claims become uncertain, never requeued."""
        authorize(identity, self.tenant, "approve")
        with self.store.transaction():
            count = 0
            for value in self.store.all(self.tenant, "external_action"):
                action = ExternalAction.model_validate(value)
                if action.state == "IN_FLIGHT" and action.last_attempt_at and action.last_attempt_at < before:
                    action.state = "UNCERTAIN"
                    action.uncertain_result = action.reconciliation_required = True
                    self.save(action)
                    self.audit(identity, action, "EXTERNAL_ACTION_ABANDONED", "abandoned_claim")
                    count += 1
            return count
