"""Demo Ascend load-status writes. Not LIVE_VALIDATED."""

from __future__ import annotations

import hmac
import secrets

from pydantic import Field

from app.core.config import Settings
from app.models.domain import ActionPolicy, AuditEvent, Model, utcnow
from app.services.ascend_notes import (
    APPROVAL_TTL,
    CLAIM_TTL,
    EVIDENCE_CLASS,
    EXECUTE_TTL,
    _aware,
    _diag,
    require_load_id,
)
from app.services.auth_tokens import token_digest
from app.services.mail_sync import digest
from app.services.portable_leases import LOAD_STATUSES

STATUS_ACTION = "ASCEND_CHANGE_LOAD_STATUS"
STATUS_ACTION_VIA_SAVE = "ASCEND_CHANGE_LOAD_STATUS_VIA_SAVE"
WRITE_KIND = "LOAD_STATUS"
WRITE_STATUSES = frozenset(status for status in LOAD_STATUSES if status != "UNKNOWN")
WHOLE_FORM_SAVE_RISK = (
    "Atlas (Booking Logistics): Load Status is a labeled select/input on Load Basics. "
    "No per-field save was observed; Save / Save & Exit submits the whole load form. "
    "Any catalog status except UNKNOWN may be requested. FreightDesk does not invent a "
    "from→to transition graph — Ascend may reject some UI transitions; VERIFIED requires "
    "read-back of the requested status."
)


class StatusWriteBody(Model):
    status: str = Field(min_length=1, max_length=32)
    approval_token: str | None = Field(default=None, max_length=256, repr=False)


def normalize_status(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("status_invalid")
    text = " ".join(value.replace("\x00", "").split())
    match = next((item for item in WRITE_STATUSES if item.casefold() == text.casefold()), None)
    if match is None:
        raise ValueError("status_not_allowed")
    return match


class AscendStatusService:
    def __init__(self, store, tenant: str, policies, portable):
        self.store = store
        self.tenant = tenant
        self.policies = policies
        self.portable = portable
        self.executor = None

    def mint_approval(self, actor_id: str, action: str, load_id: str, status: str | None = None,
                      allow_whole_form_save: bool = False) -> dict:
        self._require_demo()
        load_id = require_load_id(load_id)
        if action == STATUS_ACTION_VIA_SAVE:
            allow_whole_form_save = True
        elif action != STATUS_ACTION:
            raise ValueError("approval_action_unsupported")
        if self.policies.evaluate(STATUS_ACTION) == ActionPolicy.FORBIDDEN:
            raise PermissionError("policy_forbidden")
        status_value = normalize_status(status) if status is not None else None
        status_digest = digest(status_value) if status_value is not None else None
        token = secrets.token_urlsafe(32)
        now = utcnow()
        record = {
            "id": secrets.token_hex(16),
            "token_digest": token_digest(token),
            "action": STATUS_ACTION,
            "load_id": load_id,
            "status_digest": status_digest,
            "status": "ISSUED",
            "requested_status": status_value,
            "actor_id": actor_id,
            "created_at": now.isoformat(),
            "expires_at": (now + APPROVAL_TTL).isoformat(),
            "consumed_at": None,
            "write_id": None,
            "one_use": True,
            "allow_whole_form_save": bool(allow_whole_form_save),
            "commit_kind": "WHOLE_FORM_SAVE" if allow_whole_form_save else None,
        }
        with self.store.transaction():
            self.store.put(self.tenant, "ascend_status_approval", record["id"], record)
            self._audit("ASCEND_STATUS_APPROVAL_MINTED",
                        "Demo one-use approval minted for a load status change.",
                        {"approval_id": record["id"], "load_id": load_id, "action": STATUS_ACTION,
                         "status_bound": status_value is not None,
                         "allow_whole_form_save": bool(allow_whole_form_save)},
                        actor_id)
        how = ("Pass approval_token to POST /v1/ascend/loads/{load_id}/status. "
               "Dashboard mint or this endpoint is the demo grant; default policy is APPROVAL_REQUIRED.")
        if allow_whole_form_save:
            how = ("This approval acknowledges commit_kind=WHOLE_FORM_SAVE. Bridge may click "
                   "stay-on-load Save (preferred) or Save & Exit to persist Load Status. "
                   + WHOLE_FORM_SAVE_RISK)
        return {
            "approval_id": record["id"],
            "approval_token": token,
            "action": STATUS_ACTION,
            "load_id": load_id,
            "status_bound": status_value is not None,
            "requested_status": status_value,
            "status_digest": status_digest,
            "expires_at": record["expires_at"],
            "one_use": True,
            "allow_whole_form_save": bool(allow_whole_form_save),
            "commit_kind": "WHOLE_FORM_SAVE" if allow_whole_form_save else None,
            "whole_form_save_risk": WHOLE_FORM_SAVE_RISK if allow_whole_form_save else None,
            "allowed_statuses": sorted(WRITE_STATUSES),
            "policy": str(self.policies.evaluate(STATUS_ACTION)),
            "live_validated": False,
            "production_writes": False,
            "how": how,
        }

    def change_status(self, actor_id: str, load_id: str, status: str,
                      approval_token: str | None) -> tuple[int, dict]:
        self._require_demo()
        load_id = require_load_id(load_id)
        status = normalize_status(status)
        status_digest = digest(status)
        policy = self.policies.evaluate(STATUS_ACTION)
        now = utcnow()
        if policy == ActionPolicy.FORBIDDEN:
            receipt = self._new_receipt(actor_id, load_id, status, "FAILED", now,
                                        error_code="policy_forbidden")
            self._persist_write(receipt, actor_id, "ASCEND_STATUS_FORBIDDEN")
            return 403, self._public(receipt)
        approval = None
        if policy == ActionPolicy.APPROVAL_REQUIRED or approval_token:
            try:
                approval = self._consume_approval(approval_token, load_id, status_digest, now)
            except PermissionError as exc:
                receipt = self._new_receipt(actor_id, load_id, status, "PENDING_APPROVAL", now,
                                            error_code=str(exc))
                self._persist_write(receipt, actor_id, "ASCEND_STATUS_APPROVAL_REQUIRED")
                return 403, self._public(receipt)
        receipt = self._new_receipt(
            actor_id, load_id, status, "DISPATCHED", now,
            approval_id=None if approval is None else approval["id"],
            allow_whole_form_save=bool(approval and approval.get("allow_whole_form_save")))
        self._persist_write(receipt, actor_id, "ASCEND_STATUS_DISPATCHED")
        if approval is not None:
            approval["write_id"] = receipt["write_id"]
            self.store.put(self.tenant, "ascend_status_approval", approval["id"], approval)
        return self._finish_dispatched(receipt)

    def has_write(self, write_id: str) -> bool:
        try:
            self.store.get(self.tenant, "ascend_status_write", write_id)
            return True
        except KeyError:
            return False

    def get_write(self, write_id: str) -> dict:
        self._require_demo()
        self._expire_stale_writes(utcnow())
        return self._public(self.store.get(self.tenant, "ascend_status_write", write_id))

    def claimable(self, principal_id: str) -> list[dict]:
        return [item for item in self.store.all(self.tenant, "ascend_status_write")
                if item["status"] == "DISPATCHED" and (
                    not item.get("claimed_at") or item.get("claimed_by") == principal_id)]

    def expire_stale(self, now=None) -> list[dict]:
        return self._expire_stale_writes(now or utcnow())

    def claim_record(self, record: dict, principal: dict, now=None) -> dict:
        self._require_demo()
        now = now or utcnow()
        with self.store.transaction():
            current = self.store.get(self.tenant, "ascend_status_write", record["id"])
            if current["status"] != "DISPATCHED":
                raise ValueError("write_not_claimable")
            if current.get("claimed_by") and current["claimed_by"] != principal["id"]:
                raise PermissionError("write_not_owned")
            current["claimed_at"] = current.get("claimed_at") or now.isoformat()
            current["claimed_by"] = principal["id"]
            current["stage"] = "claimed"
            self.store.put(self.tenant, "ascend_status_write", current["id"], current)
            self._audit("ASCEND_STATUS_CLAIMED", "Portable bridge claimed a load-status write.",
                        {"write_id": current["id"], "load_id": current["load_id"]},
                        principal["id"])
        return {
            "pending": True,
            "write_id": current["id"],
            "action": "CHANGE_LOAD_STATUS",
            "policy_action": STATUS_ACTION,
            "write_kind": WRITE_KIND,
            "load_id": current["load_id"],
            "status": current["requested_status"],
            "requested_status": current["requested_status"],
            "allow_whole_form_save": bool(current.get("allow_whole_form_save")),
            "commit_kind": "WHOLE_FORM_SAVE" if current.get("allow_whole_form_save") else None,
            "live_validated": False,
            "production_writes": False,
        }

    def complete(self, token: str, write_id: str, verified: bool, status_matched: bool,
                 observed_status: str | None, error_code: str | None, live_validated: bool,
                 production_writes: bool, stage: str | None = None,
                 opener_strategy: str | None = None, commit_kind: str | None = None,
                 save_variant: str | None = None, tab_hint: str | None = None,
                 reopen_attempts: int | None = None, verify_reason: str | None = None,
                 bridge_version: str | None = None) -> dict:
        self._require_demo()
        principal = self.portable._require_principal(token)
        if live_validated or production_writes:
            raise ValueError("live_validated_or_production_writes_forbidden")
        now = utcnow()
        observed = None
        if observed_status:
            try:
                observed = normalize_status(observed_status)
            except ValueError:
                observed = _diag(observed_status, 32)
        with self.store.transaction():
            record = self.store.get(self.tenant, "ascend_status_write", write_id)
            if record["status"] not in {"DISPATCHED"}:
                raise ValueError("write_not_completable")
            if record.get("claimed_by") and record["claimed_by"] != principal["id"]:
                raise PermissionError("write_not_owned")
            matched = bool(status_matched and observed == record["requested_status"])
            status, code = self._verify_outcome(verified, matched, _diag(error_code))
            record.update(status=status, verified=status == "VERIFIED",
                          status_matched=matched, observed_status=observed,
                          error_code=code, completed_at=now.isoformat(), completed_by=principal["id"],
                          stage=_diag(stage), opener_strategy=_diag(opener_strategy),
                          commit_kind=_diag(commit_kind),
                          save_variant=_diag(save_variant, 32),
                          tab_hint=_diag(tab_hint, 80) or "missing",
                          reopen_attempts=reopen_attempts if reopen_attempts is not None else 0,
                          verify_reason=_diag(verify_reason, 64),
                          bridge_version=_diag(bridge_version, 16))
            self.store.put(self.tenant, "ascend_status_write", record["id"], record)
            self._audit("ASCEND_STATUS_" + status, "Load-status write completed with verify-after-write.",
                        {"write_id": record["id"], "load_id": record["load_id"],
                         "requested_status": record["requested_status"],
                         "observed_status": observed, "status_matched": matched,
                         "error_code": code, "stage": record.get("stage"),
                         "opener_strategy": record.get("opener_strategy"),
                         "commit_kind": record.get("commit_kind"),
                         "save_variant": record.get("save_variant"),
                         "tab_hint": record.get("tab_hint"),
                         "reopen_attempts": record.get("reopen_attempts"),
                         "verify_reason": record.get("verify_reason"),
                         "bridge_version": record.get("bridge_version"),
                         "allow_whole_form_save": bool(record.get("allow_whole_form_save"))},
                        principal["id"])
        return self._public(record)

    def _finish_dispatched(self, receipt: dict) -> tuple[int, dict]:
        executor = self.executor
        if executor is None:
            return 200, self._public(receipt)
        try:
            result = executor({
                "load_id": receipt["load_id"],
                "status": receipt["requested_status"],
                "action": STATUS_ACTION,
                "allow_whole_form_save": bool(receipt.get("allow_whole_form_save")),
            })
        except Exception:
            result = {"verified": False, "status_matched": False, "error_code": "executor_failed"}
        observed = result.get("observed_status") or result.get("status")
        try:
            observed = normalize_status(observed) if observed else None
        except ValueError:
            observed = _diag(observed, 32)
        matched = bool(result.get("status_matched") and observed == receipt["requested_status"])
        status, code = self._verify_outcome(bool(result.get("verified")), matched,
                                            result.get("error_code"))
        now = utcnow()
        with self.store.transaction():
            record = self.store.get(self.tenant, "ascend_status_write", receipt["write_id"])
            record.update(status=status, verified=status == "VERIFIED",
                          status_matched=matched, observed_status=observed, error_code=code,
                          completed_at=now.isoformat(), completed_by="fixture-executor",
                          stage=_diag(result.get("stage")),
                          opener_strategy=_diag(result.get("opener_strategy")),
                          commit_kind=_diag(result.get("commit_kind")),
                          save_variant=_diag(result.get("save_variant"), 32))
            self.store.put(self.tenant, "ascend_status_write", record["id"], record)
            self._audit("ASCEND_STATUS_" + status, "Fixture executor finished verify-after-write.",
                        {"write_id": record["id"], "load_id": record["load_id"],
                         "status_matched": matched, "error_code": code},
                        receipt["actor_id"])
        return 200, self._public(record)

    def _consume_approval(self, token: str | None, load_id: str, status_digest: str, now) -> dict:
        if not token:
            raise PermissionError("approval_required")
        digest_value = token_digest(token)
        with self.store.transaction():
            match = next((item for item in self.store.all(self.tenant, "ascend_status_approval")
                          if hmac.compare_digest(item["token_digest"], digest_value)), None)
            if match is None:
                raise PermissionError("approval_invalid")
            if match["status"] != "ISSUED":
                raise PermissionError("approval_consumed")
            if match["expires_at"] <= now.isoformat():
                match["status"] = "EXPIRED"
                self.store.put(self.tenant, "ascend_status_approval", match["id"], match)
                raise PermissionError("approval_expired")
            if match["action"] != STATUS_ACTION or match["load_id"] != load_id:
                raise PermissionError("approval_binding_invalid")
            if match.get("status_digest") and match["status_digest"] != status_digest:
                raise PermissionError("approval_status_mismatch")
            match["status"] = "CONSUMED"
            match["consumed_at"] = now.isoformat()
            self.store.put(self.tenant, "ascend_status_approval", match["id"], match)
            return match

    def _new_receipt(self, actor_id: str, load_id: str, requested_status: str, status: str, now,
                     error_code: str | None = None, approval_id: str | None = None,
                     allow_whole_form_save: bool = False) -> dict:
        write_id = secrets.token_hex(16)
        return {
            "id": write_id,
            "receipt_id": write_id,
            "write_id": write_id,
            "action": STATUS_ACTION,
            "write_kind": WRITE_KIND,
            "load_id": load_id,
            "requested_status": requested_status,
            "observed_status": None,
            "status": status,
            "evidence_class": EVIDENCE_CLASS,
            "live_validated": False,
            "production_writes": False,
            "policy": str(self.policies.evaluate(STATUS_ACTION)),
            "verified": False,
            "status_matched": False,
            "error_code": error_code,
            "approval_id": approval_id,
            "actor_id": actor_id,
            "created_at": now.isoformat(),
            "dispatched_at": now.isoformat() if status == "DISPATCHED" else None,
            "completed_at": None,
            "claimed_at": None,
            "claimed_by": None,
            "claim_deadline_at": (now + CLAIM_TTL).isoformat() if status == "DISPATCHED" else None,
            "stage": "awaiting_bridge" if status == "DISPATCHED" else None,
            "opener_strategy": None,
            "commit_kind": "WHOLE_FORM_SAVE" if allow_whole_form_save else None,
            "save_variant": None,
            "tab_hint": None,
            "reopen_attempts": None,
            "verify_reason": None,
            "bridge_version": None,
            "allow_whole_form_save": bool(allow_whole_form_save),
            "allowed_statuses": sorted(WRITE_STATUSES),
        }

    def _persist_write(self, receipt: dict, actor_id: str, event: str):
        with self.store.transaction():
            self.store.put(self.tenant, "ascend_status_write", receipt["write_id"], receipt)
            self._audit(event, "Load-status write receipt recorded.",
                        {"write_id": receipt["write_id"], "load_id": receipt["load_id"],
                         "requested_status": receipt["requested_status"],
                         "status": receipt["status"], "error_code": receipt["error_code"]},
                        actor_id)

    def _public(self, record: dict) -> dict:
        public = {key: record.get(key) for key in (
            "receipt_id", "write_id", "action", "write_kind", "load_id", "requested_status",
            "observed_status", "status", "evidence_class", "live_validated", "production_writes",
            "policy", "verified", "status_matched", "error_code", "approval_id", "created_at",
            "dispatched_at", "completed_at", "claimed_at", "claim_deadline_at", "stage",
            "opener_strategy", "commit_kind", "save_variant",
            "tab_hint", "reopen_attempts", "verify_reason", "bridge_version",
            "allow_whole_form_save", "allowed_statuses")}
        public["whole_form_save_risk"] = (
            WHOLE_FORM_SAVE_RISK if record.get("allow_whole_form_save")
            or record.get("commit_kind") == "WHOLE_FORM_SAVE" else None)
        public["silent_save_forbidden"] = True
        return public

    def _expire_stale_writes(self, now) -> list[dict]:
        expired = []
        for record in list(self.store.all(self.tenant, "ascend_status_write")):
            if record.get("status") != "DISPATCHED":
                continue
            claimed = _aware(record.get("claimed_at"))
            started = _aware(record.get("dispatched_at") or record.get("created_at"))
            if started is None:
                continue
            limit = EXECUTE_TTL if claimed else CLAIM_TTL
            age_from = claimed or started
            if now - age_from < limit:
                continue
            record.update(status="FAILED", verified=False, status_matched=False,
                          error_code="BRIDGE_CLAIM_TIMEOUT", stage="claim",
                          completed_at=now.isoformat())
            self.store.put(self.tenant, "ascend_status_write", record["id"], record)
            self._audit("ASCEND_STATUS_FAILED", "Unclaimed or unfinished status write timed out.",
                        {"write_id": record["id"], "load_id": record["load_id"],
                         "error_code": "BRIDGE_CLAIM_TIMEOUT"},
                        record.get("claimed_by") or record.get("actor_id") or "bridge")
            expired.append(record)
        return expired

    def _verify_outcome(self, verified: bool, status_matched: bool,
                        error_code: str | None) -> tuple[str, str | None]:
        if verified and status_matched:
            return "VERIFIED", None
        if verified and not status_matched:
            return "FAILED", "verify_without_status_match"
        return "FAILED", error_code or "status_not_matched"

    def _require_demo(self):
        if Settings.from_env().mode != "demo":
            raise PermissionError("demo_mode_required")

    def _audit(self, event: str, explanation: str, facts: dict, actor_id: str):
        self.store.audit(AuditEvent(
            tenant_id=self.tenant,
            actor_id=actor_id,
            source="ascend_status_v0",
            event=event,
            explanation=explanation,
            facts=facts,
            action=STATUS_ACTION,
            policy=self.policies.evaluate(STATUS_ACTION),
            verified=False,
        ))
