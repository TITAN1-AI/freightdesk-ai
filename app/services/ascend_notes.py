"""Demo Ascend private-internal-note writes. Not LIVE_VALIDATED."""

from __future__ import annotations

import hmac
import re
import secrets
from datetime import timedelta

from pydantic import Field

from app.core.config import Settings
from app.models.domain import ActionPolicy, AuditEvent, Model, utcnow
from app.services.auth_tokens import token_digest
from app.services.mail_sync import digest

NOTE_ACTION = "ASCEND_ADD_INTERNAL_NOTE"
NOTE_KIND = "PRIVATE_INTERNAL"
MAX_NOTE_CHARS = 4000
LOAD_ID = re.compile(r"^\d{1,20}$")
APPROVAL_TTL = timedelta(minutes=15)
EVIDENCE_CLASS = "CANDIDATE"


class ApprovalMintBody(Model):
    action: str = Field(min_length=8, max_length=64)
    load_id: str = Field(min_length=1, max_length=20)
    text: str | None = Field(default=None, max_length=MAX_NOTE_CHARS, repr=False)


class NoteWriteBody(Model):
    text: str = Field(min_length=1, max_length=MAX_NOTE_CHARS, repr=False)
    approval_token: str | None = Field(default=None, max_length=256, repr=False)


class WriteCompleteBody(Model):
    verified: bool
    note_present: bool
    error_code: str | None = Field(default=None, max_length=64)
    live_validated: bool = False
    production_writes: bool = False


def normalize_note_text(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("note_text_invalid")
    text = value.replace("\x00", "").strip()
    if not text or len(text) > MAX_NOTE_CHARS:
        raise ValueError("note_text_invalid")
    return text


def require_load_id(load_id: str) -> str:
    if not LOAD_ID.fullmatch(load_id or ""):
        raise ValueError("load_id_invalid")
    return load_id


class AscendNoteService:
    def __init__(self, store, tenant: str, policies, portable):
        self.store = store
        self.tenant = tenant
        self.policies = policies
        self.portable = portable
        self.executor = None

    def mint_approval(self, actor_id: str, action: str, load_id: str, text: str | None = None) -> dict:
        self._require_demo()
        load_id = require_load_id(load_id)
        if action != NOTE_ACTION:
            raise ValueError("approval_action_unsupported")
        if self.policies.evaluate(NOTE_ACTION) == ActionPolicy.FORBIDDEN:
            raise PermissionError("policy_forbidden")
        text_digest = digest(normalize_note_text(text)) if text is not None else None
        token = secrets.token_urlsafe(32)
        now = utcnow()
        record = {
            "id": secrets.token_hex(16),
            "token_digest": token_digest(token),
            "action": NOTE_ACTION,
            "load_id": load_id,
            "text_digest": text_digest,
            "status": "ISSUED",
            "actor_id": actor_id,
            "created_at": now.isoformat(),
            "expires_at": (now + APPROVAL_TTL).isoformat(),
            "consumed_at": None,
            "write_id": None,
            "one_use": True,
        }
        with self.store.transaction():
            self.store.put(self.tenant, "ascend_note_approval", record["id"], record)
            self._audit("ASCEND_NOTE_APPROVAL_MINTED",
                        "Demo one-use approval minted for a private internal note.",
                        {"approval_id": record["id"], "load_id": load_id, "action": NOTE_ACTION},
                        actor_id)
        return {
            "approval_id": record["id"],
            "approval_token": token,
            "action": NOTE_ACTION,
            "load_id": load_id,
            "text_bound": text_digest is not None,
            "text_digest": text_digest,
            "expires_at": record["expires_at"],
            "one_use": True,
            "policy": str(self.policies.evaluate(NOTE_ACTION)),
            "live_validated": False,
            "production_writes": False,
            "how": "Pass approval_token to POST /v1/ascend/loads/{load_id}/notes. "
                   "Dashboard button or this mint is the demo grant; default policy is APPROVAL_REQUIRED.",
        }

    def add_note(self, actor_id: str, load_id: str, text: str, approval_token: str | None) -> tuple[int, dict]:
        self._require_demo()
        load_id = require_load_id(load_id)
        text = normalize_note_text(text)
        text_digest = digest(text)
        policy = self.policies.evaluate(NOTE_ACTION)
        now = utcnow()
        if policy == ActionPolicy.FORBIDDEN:
            receipt = self._new_receipt(actor_id, load_id, text_digest, "FAILED", now,
                                        error_code="policy_forbidden")
            self._persist_write(receipt, text, actor_id, "ASCEND_NOTE_FORBIDDEN")
            return 403, receipt
        approval = None
        if policy == ActionPolicy.APPROVAL_REQUIRED or approval_token:
            try:
                approval = self._consume_approval(approval_token, load_id, text_digest, now)
            except PermissionError as exc:
                receipt = self._new_receipt(actor_id, load_id, text_digest, "PENDING_APPROVAL", now,
                                            error_code=str(exc))
                self._persist_write(receipt, None, actor_id, "ASCEND_NOTE_APPROVAL_REQUIRED")
                return 403, receipt
        receipt = self._new_receipt(actor_id, load_id, text_digest, "DISPATCHED", now,
                                    approval_id=None if approval is None else approval["id"])
        self._persist_write(receipt, text, actor_id, "ASCEND_NOTE_DISPATCHED")
        if approval is not None:
            approval["write_id"] = receipt["write_id"]
            self.store.put(self.tenant, "ascend_note_approval", approval["id"], approval)
        return self._finish_dispatched(receipt, text)

    def get_write(self, write_id: str) -> dict:
        self._require_demo()
        return self._public(self.store.get(self.tenant, "ascend_note_write", write_id))

    def claim_pending(self, token: str) -> dict:
        self._require_demo()
        principal = self.portable._require_principal(token)
        now = utcnow()
        with self.store.transaction():
            pending = [item for item in self.store.all(self.tenant, "ascend_note_write")
                       if item["status"] == "DISPATCHED" and not item.get("claimed_at")]
            if not pending:
                return {"pending": False, "action": NOTE_ACTION, "live_validated": False}
            record = sorted(pending, key=lambda item: item["created_at"])[0]
            record["claimed_at"] = now.isoformat()
            record["claimed_by"] = principal["id"]
            self.store.put(self.tenant, "ascend_note_write", record["id"], record)
            secret = self.store.get(self.tenant, "ascend_note_secret", record["id"])
            self._audit("ASCEND_NOTE_CLAIMED", "Portable bridge claimed a private-note write.",
                        {"write_id": record["id"], "load_id": record["load_id"]},
                        principal["id"])
        return {
            "pending": True,
            "write_id": record["id"],
            "action": "ADD_INTERNAL_NOTE",
            "policy_action": NOTE_ACTION,
            "note_kind": NOTE_KIND,
            "load_id": record["load_id"],
            "text": secret["text"],
            "text_digest": record["text_digest"],
            "live_validated": False,
            "production_writes": False,
        }

    def complete(self, token: str, write_id: str, verified: bool, note_present: bool,
                 error_code: str | None, live_validated: bool, production_writes: bool) -> dict:
        self._require_demo()
        principal = self.portable._require_principal(token)
        if live_validated or production_writes:
            raise ValueError("live_validated_or_production_writes_forbidden")
        now = utcnow()
        with self.store.transaction():
            record = self.store.get(self.tenant, "ascend_note_write", write_id)
            if record["status"] not in {"DISPATCHED"}:
                raise ValueError("write_not_completable")
            if record.get("claimed_by") and record["claimed_by"] != principal["id"]:
                raise PermissionError("write_not_owned")
            status, code = self._verify_outcome(verified, note_present, error_code)
            record.update(status=status, verified=status == "VERIFIED", note_present=note_present,
                          error_code=code, completed_at=now.isoformat(), completed_by=principal["id"])
            self.store.put(self.tenant, "ascend_note_write", record["id"], record)
            self._audit("ASCEND_NOTE_" + status, "Private-note write completed with verify-after-write.",
                        {"write_id": record["id"], "load_id": record["load_id"], "note_present": note_present,
                         "error_code": code}, principal["id"])
        return self._public(record)

    def _finish_dispatched(self, receipt: dict, text: str) -> tuple[int, dict]:
        executor = self.executor
        if executor is None:
            return 200, receipt
        try:
            result = executor({"load_id": receipt["load_id"], "text": text,
                               "text_digest": receipt["text_digest"], "action": NOTE_ACTION})
        except Exception:
            result = {"verified": False, "note_present": False, "error_code": "executor_failed"}
        status, code = self._verify_outcome(bool(result.get("verified")), bool(result.get("note_present")),
                                            result.get("error_code"))
        now = utcnow()
        with self.store.transaction():
            record = self.store.get(self.tenant, "ascend_note_write", receipt["write_id"])
            record.update(status=status, verified=status == "VERIFIED",
                          note_present=bool(result.get("note_present")), error_code=code,
                          completed_at=now.isoformat(), completed_by="fixture-executor")
            self.store.put(self.tenant, "ascend_note_write", record["id"], record)
            self._audit("ASCEND_NOTE_" + status, "Fixture executor finished verify-after-write.",
                        {"write_id": record["id"], "load_id": record["load_id"],
                         "note_present": record["note_present"], "error_code": code},
                        receipt["actor_id"])
        return 200, self._public(record)

    def _consume_approval(self, token: str | None, load_id: str, text_digest: str, now) -> dict:
        if not token:
            raise PermissionError("approval_required")
        digest_value = token_digest(token)
        with self.store.transaction():
            match = next((item for item in self.store.all(self.tenant, "ascend_note_approval")
                          if hmac.compare_digest(item["token_digest"], digest_value)), None)
            if match is None:
                raise PermissionError("approval_invalid")
            if match["status"] != "ISSUED":
                raise PermissionError("approval_consumed")
            if match["expires_at"] <= now.isoformat():
                match["status"] = "EXPIRED"
                self.store.put(self.tenant, "ascend_note_approval", match["id"], match)
                raise PermissionError("approval_expired")
            if match["action"] != NOTE_ACTION or match["load_id"] != load_id:
                raise PermissionError("approval_binding_invalid")
            if match["text_digest"] and match["text_digest"] != text_digest:
                raise PermissionError("approval_text_mismatch")
            match["status"] = "CONSUMED"
            match["consumed_at"] = now.isoformat()
            self.store.put(self.tenant, "ascend_note_approval", match["id"], match)
            return match

    def _new_receipt(self, actor_id: str, load_id: str, text_digest: str, status: str, now,
                     error_code: str | None = None, approval_id: str | None = None) -> dict:
        write_id = secrets.token_hex(16)
        return {
            "id": write_id,
            "receipt_id": write_id,
            "write_id": write_id,
            "action": NOTE_ACTION,
            "note_kind": NOTE_KIND,
            "load_id": load_id,
            "status": status,
            "evidence_class": EVIDENCE_CLASS,
            "live_validated": False,
            "production_writes": False,
            "policy": str(self.policies.evaluate(NOTE_ACTION)),
            "verified": False,
            "note_present": False,
            "text_digest": text_digest,
            "error_code": error_code,
            "approval_id": approval_id,
            "actor_id": actor_id,
            "created_at": now.isoformat(),
            "dispatched_at": now.isoformat() if status == "DISPATCHED" else None,
            "completed_at": None,
            "claimed_at": None,
            "claimed_by": None,
        }

    def _persist_write(self, receipt: dict, text: str | None, actor_id: str, event: str):
        with self.store.transaction():
            self.store.put(self.tenant, "ascend_note_write", receipt["write_id"], receipt)
            if text is not None:
                self.store.put(self.tenant, "ascend_note_secret", receipt["write_id"], {
                    "id": receipt["write_id"],
                    "text_digest": receipt["text_digest"],
                    "text": text,
                })
            self._audit(event, "Private-note write receipt recorded. Text omitted.",
                        {"write_id": receipt["write_id"], "load_id": receipt["load_id"],
                         "status": receipt["status"], "error_code": receipt["error_code"]},
                        actor_id)

    def _public(self, record: dict) -> dict:
        return {key: record.get(key) for key in (
            "receipt_id", "write_id", "action", "note_kind", "load_id", "status",
            "evidence_class", "live_validated", "production_writes", "policy", "verified",
            "note_present", "text_digest", "error_code", "approval_id", "created_at",
            "dispatched_at", "completed_at")}

    def _verify_outcome(self, verified: bool, note_present: bool, error_code: str | None) -> tuple[str, str | None]:
        if verified and note_present:
            return "VERIFIED", None
        if verified and not note_present:
            return "FAILED", "verify_without_presence"
        return "FAILED", error_code or "note_not_present"

    def _require_demo(self):
        if Settings.from_env().mode != "demo":
            raise PermissionError("demo_mode_required")

    def _audit(self, event: str, explanation: str, facts: dict, actor_id: str):
        self.store.audit(AuditEvent(
            tenant_id=self.tenant,
            actor_id=actor_id,
            source="ascend_note_v0",
            event=event,
            explanation=explanation,
            facts=facts,
            action=NOTE_ACTION,
            policy=self.policies.evaluate(NOTE_ACTION),
            verified=False,
        ))
