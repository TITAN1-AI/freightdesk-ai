"""Demo Ascend private/public note read-back. ALLOW, not LIVE_VALIDATED."""

from __future__ import annotations

import secrets

from app.core.config import Settings
from app.models.domain import ActionPolicy, AuditEvent, utcnow
from app.services.ascend_atlas import PRIVATE_NOTE_SELECTOR, PUBLIC_NOTE_SELECTOR
from app.services.ascend_notes import (
    CLAIM_TTL,
    EVIDENCE_CLASS,
    EXECUTE_TTL,
    MAX_NOTE_CHARS,
    _aware,
    _diag,
    require_load_id,
)
from app.services.mail_sync import digest

READ_ACTION = "ASCEND_READ_LOAD_NOTES"
READ_KIND = "LOAD_NOTES"
BRIDGE_ACTION = "READ_LOAD_NOTES"


def normalize_observed_note(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("note_text_invalid")
    text = value.replace("\x00", "")
    if len(text) > MAX_NOTE_CHARS:
        text = text[:MAX_NOTE_CHARS]
    return text


class AscendNoteReadService:
    def __init__(self, store, tenant: str, policies, portable):
        self.store = store
        self.tenant = tenant
        self.policies = policies
        self.portable = portable
        self.executor = None

    def capture(self, actor_id: str, load_id: str) -> tuple[int, dict]:
        self._require_demo()
        load_id = require_load_id(load_id)
        policy = self.policies.evaluate(READ_ACTION)
        now = utcnow()
        if policy == ActionPolicy.FORBIDDEN:
            receipt = self._new_receipt(actor_id, load_id, "FAILED", now, error_code="policy_forbidden")
            self._persist(receipt, actor_id, "ASCEND_NOTE_READ_FORBIDDEN")
            return 403, receipt
        if policy == ActionPolicy.APPROVAL_REQUIRED:
            receipt = self._new_receipt(actor_id, load_id, "PENDING_APPROVAL", now,
                                        error_code="approval_required")
            self._persist(receipt, actor_id, "ASCEND_NOTE_READ_APPROVAL_REQUIRED")
            return 403, receipt
        receipt = self._new_receipt(actor_id, load_id, "DISPATCHED", now)
        self._persist(receipt, actor_id, "ASCEND_NOTE_READ_DISPATCHED")
        return self._finish_dispatched(receipt)

    def latest(self, load_id: str) -> dict:
        self._require_demo()
        identity = require_load_id(load_id)
        self._expire_stale(utcnow())
        captures = [item for item in self.store.all(self.tenant, "ascend_note_capture")
                    if item.get("load_id") == identity and item.get("status") == "VERIFIED"]
        captures.sort(key=lambda item: item.get("completed_at") or item.get("created_at") or "")
        record = captures[-1] if captures else None
        secret = None
        if record is not None:
            try:
                secret = self.store.get(self.tenant, "ascend_note_capture_secret", record["id"])
            except KeyError:
                secret = None
        return self._latest_public(identity, record, secret)

    def has_write(self, write_id: str) -> bool:
        try:
            self.store.get(self.tenant, "ascend_note_capture", write_id)
            return True
        except KeyError:
            return False

    def get_write(self, write_id: str) -> dict:
        self._require_demo()
        self._expire_stale(utcnow())
        record = self.store.get(self.tenant, "ascend_note_capture", write_id)
        secret = None
        try:
            secret = self.store.get(self.tenant, "ascend_note_capture_secret", write_id)
        except KeyError:
            secret = None
        return self._public(record, secret)

    def claimable(self, principal_id: str) -> list[dict]:
        return [item for item in self.store.all(self.tenant, "ascend_note_capture")
                if item["status"] == "DISPATCHED" and (
                    not item.get("claimed_at") or item.get("claimed_by") == principal_id)]

    def expire_stale(self, now=None) -> list[dict]:
        return self._expire_stale(now or utcnow())

    def claim_record(self, record: dict, principal: dict, now=None) -> dict:
        self._require_demo()
        now = now or utcnow()
        with self.store.transaction():
            current = self.store.get(self.tenant, "ascend_note_capture", record["id"])
            if current["status"] != "DISPATCHED":
                raise ValueError("write_not_claimable")
            if current.get("claimed_by") and current["claimed_by"] != principal["id"]:
                raise PermissionError("write_not_owned")
            current["claimed_at"] = current.get("claimed_at") or now.isoformat()
            current["claimed_by"] = principal["id"]
            current["stage"] = "claimed"
            self.store.put(self.tenant, "ascend_note_capture", current["id"], current)
            self._audit("ASCEND_NOTE_READ_CLAIMED", "Portable bridge claimed a load-note read-back.",
                        {"write_id": current["id"], "load_id": current["load_id"]},
                        principal["id"])
        return {
            "pending": True,
            "write_id": current["id"],
            "action": BRIDGE_ACTION,
            "policy_action": READ_ACTION,
            "read_kind": READ_KIND,
            "load_id": current["load_id"],
            "allow_whole_form_save": False,
            "commit_kind": "READ_ONLY",
            "live_validated": False,
            "production_writes": False,
            "silent_save_forbidden": True,
        }

    def complete(self, token: str, write_id: str, verified: bool, error_code: str | None,
                 live_validated: bool, production_writes: bool, stage: str | None = None,
                 opener_strategy: str | None = None, note_label: str | None = None,
                 commit_kind: str | None = None, save_variant: str | None = None,
                 tab_hint: str | None = None, reopen_attempts: int | None = None,
                 verify_reason: str | None = None, bridge_version: str | None = None,
                 private_note: str | None = None, public_note: str | None = None,
                 private_note_present: bool = False, public_note_present: bool = False) -> dict:
        self._require_demo()
        principal = self.portable._require_principal(token)
        if live_validated or production_writes:
            raise ValueError("live_validated_or_production_writes_forbidden")
        observed_private = normalize_observed_note(private_note)
        observed_public = normalize_observed_note(public_note)
        now = utcnow()
        with self.store.transaction():
            record = self.store.get(self.tenant, "ascend_note_capture", write_id)
            if record["status"] not in {"DISPATCHED"}:
                raise ValueError("write_not_completable")
            if record.get("claimed_by") and record["claimed_by"] != principal["id"]:
                raise PermissionError("write_not_owned")
            # Empty string still means the control was found (JS sends "" vs null).
            private_present = bool(private_note_present or observed_private is not None)
            public_present = bool(public_note_present or observed_public is not None)
            status, code = self._verify_outcome(verified, private_present, public_present, _diag(error_code))
            record.update(
                status=status, verified=status == "VERIFIED",
                private_note_present=private_present, public_note_present=public_present,
                note_present=private_present,
                private_note_digest=digest(observed_private or "") if private_present else None,
                public_note_digest=digest(observed_public or "") if public_present else None,
                error_code=code, completed_at=now.isoformat(), completed_by=principal["id"],
                stage=_diag(stage), opener_strategy=_diag(opener_strategy),
                note_label=_diag(note_label, 80),
                commit_kind=_diag(commit_kind) or "READ_ONLY",
                save_variant=_diag(save_variant, 32) or "NONE",
                tab_hint=_diag(tab_hint, 80) or "missing",
                reopen_attempts=reopen_attempts if reopen_attempts is not None else 0,
                verify_reason=_diag(verify_reason, 64),
                bridge_version=_diag(bridge_version, 16),
            )
            self.store.put(self.tenant, "ascend_note_capture", record["id"], record)
            if status == "VERIFIED":
                self.store.put(self.tenant, "ascend_note_capture_secret", record["id"], {
                    "id": record["id"],
                    "load_id": record["load_id"],
                    "private_note": observed_private if private_present else None,
                    "public_note": observed_public if public_present else None,
                })
            self._audit("ASCEND_NOTE_READ_" + status, "Load-note read-back completed. Raw text omitted.",
                        {"write_id": record["id"], "load_id": record["load_id"],
                         "private_note_present": private_present, "public_note_present": public_present,
                         "error_code": code, "tab_hint": record.get("tab_hint"),
                         "verify_reason": record.get("verify_reason"),
                         "bridge_version": record.get("bridge_version")},
                        principal["id"])
        secret = None
        if status == "VERIFIED":
            secret = self.store.get(self.tenant, "ascend_note_capture_secret", record["id"])
        return self._public(record, secret)

    def _finish_dispatched(self, receipt: dict) -> tuple[int, dict]:
        executor = self.executor
        if executor is None:
            return 200, receipt
        try:
            result = executor({"load_id": receipt["load_id"], "action": READ_ACTION})
        except Exception:
            result = {"verified": False, "error_code": "executor_failed"}
        now = utcnow()
        observed_private = normalize_observed_note(result.get("private_note"))
        observed_public = normalize_observed_note(result.get("public_note"))
        private_present = bool(result.get("private_note_present") or observed_private is not None)
        public_present = bool(result.get("public_note_present") or observed_public is not None)
        status, code = self._verify_outcome(bool(result.get("verified")), private_present, public_present,
                                            result.get("error_code"))
        with self.store.transaction():
            record = self.store.get(self.tenant, "ascend_note_capture", receipt["write_id"])
            record.update(status=status, verified=status == "VERIFIED",
                          private_note_present=private_present, public_note_present=public_present,
                          note_present=private_present, error_code=code,
                          completed_at=now.isoformat(), completed_by="fixture-executor",
                          stage=_diag(result.get("stage")),
                          opener_strategy=_diag(result.get("opener_strategy")),
                          note_label=_diag(result.get("note_label"), 80),
                          commit_kind="READ_ONLY", save_variant="NONE",
                          tab_hint=_diag(result.get("tab_hint"), 80) or "fixture",
                          verify_reason=_diag(result.get("verify_reason"), 64),
                          bridge_version=_diag(result.get("bridge_version"), 16),
                          private_note_digest=digest(observed_private or "") if private_present else None,
                          public_note_digest=digest(observed_public or "") if public_present else None)
            self.store.put(self.tenant, "ascend_note_capture", record["id"], record)
            if status == "VERIFIED":
                self.store.put(self.tenant, "ascend_note_capture_secret", record["id"], {
                    "id": record["id"], "load_id": record["load_id"],
                    "private_note": observed_private if private_present else None,
                    "public_note": observed_public if public_present else None,
                })
            self._audit("ASCEND_NOTE_READ_" + status, "Fixture executor finished note read-back.",
                        {"write_id": record["id"], "load_id": record["load_id"], "error_code": code},
                        receipt["actor_id"])
        secret = None
        if status == "VERIFIED":
            secret = self.store.get(self.tenant, "ascend_note_capture_secret", record["id"])
        return 200, self._public(record, secret)

    def _new_receipt(self, actor_id: str, load_id: str, status: str, now,
                     error_code: str | None = None) -> dict:
        write_id = secrets.token_hex(16)
        return {
            "id": write_id,
            "receipt_id": write_id,
            "write_id": write_id,
            "action": READ_ACTION,
            "read_kind": READ_KIND,
            "load_id": load_id,
            "status": status,
            "evidence_class": EVIDENCE_CLASS,
            "live_validated": False,
            "production_writes": False,
            "silent_save_forbidden": True,
            "policy": str(self.policies.evaluate(READ_ACTION)),
            "verified": False,
            "note_present": False,
            "private_note_present": False,
            "public_note_present": False,
            "error_code": error_code,
            "actor_id": actor_id,
            "created_at": now.isoformat(),
            "dispatched_at": now.isoformat() if status == "DISPATCHED" else None,
            "completed_at": None,
            "claimed_at": None,
            "claimed_by": None,
            "claim_deadline_at": (now + CLAIM_TTL).isoformat() if status == "DISPATCHED" else None,
            "stage": "awaiting_bridge" if status == "DISPATCHED" else None,
            "opener_strategy": None,
            "note_label": None,
            "commit_kind": "READ_ONLY",
            "save_variant": "NONE",
            "tab_hint": None,
            "reopen_attempts": None,
            "verify_reason": None,
            "bridge_version": None,
            "allow_whole_form_save": False,
            "atlas_private": PRIVATE_NOTE_SELECTOR,
            "atlas_public": PUBLIC_NOTE_SELECTOR,
        }

    def _persist(self, receipt: dict, actor_id: str, event: str) -> None:
        with self.store.transaction():
            self.store.put(self.tenant, "ascend_note_capture", receipt["write_id"], receipt)
            self._audit(event, "Load-note read-back receipt recorded. Text omitted.",
                        {"write_id": receipt["write_id"], "load_id": receipt["load_id"],
                         "status": receipt["status"], "error_code": receipt["error_code"]},
                        actor_id)

    def _public(self, record: dict, secret: dict | None = None) -> dict:
        public = {key: record.get(key) for key in (
            "receipt_id", "write_id", "action", "read_kind", "load_id", "status",
            "evidence_class", "live_validated", "production_writes", "silent_save_forbidden",
            "policy", "verified", "note_present", "private_note_present", "public_note_present",
            "private_note_digest", "public_note_digest", "error_code", "created_at",
            "dispatched_at", "completed_at", "claimed_at", "claim_deadline_at", "stage",
            "opener_strategy", "note_label", "commit_kind", "save_variant",
            "tab_hint", "reopen_attempts", "verify_reason", "bridge_version",
            "atlas_private", "atlas_public")}
        public["private_note"] = None if secret is None else secret.get("private_note")
        public["public_note"] = None if secret is None else secret.get("public_note")
        public["whole_form_save_risk"] = None
        public["allow_whole_form_save"] = False
        return public

    def _latest_public(self, load_id: str, record: dict | None, secret: dict | None) -> dict:
        found = record is not None
        return {
            "facade": "ascend",
            "source": "portable_note_capture" if found else "none",
            "not_a_retail_api": True,
            "section": "Load Basics",
            "load_id": load_id,
            "found": found,
            "evidence_class": EVIDENCE_CLASS,
            "live_validated": False,
            "production_writes": False,
            "silent_save_forbidden": True,
            "policy": "ALLOW",
            "atlas_private": PRIVATE_NOTE_SELECTOR,
            "atlas_public": PUBLIC_NOTE_SELECTOR,
            "private_note": None if secret is None else secret.get("private_note"),
            "public_note": None if secret is None else secret.get("public_note"),
            "private_note_present": False if record is None else bool(record.get("private_note_present")),
            "public_note_present": False if record is None else bool(record.get("public_note_present")),
            "captured_at": None if record is None else record.get("completed_at"),
            "capture_id": None if record is None else record.get("write_id"),
            "tab_hint": None if record is None else record.get("tab_hint"),
            "verify_reason": None if record is None else record.get("verify_reason"),
            "bridge_version": None if record is None else record.get("bridge_version"),
            "opener_strategy": None if record is None else record.get("opener_strategy"),
        }

    def _expire_stale(self, now) -> list[dict]:
        expired = []
        for record in list(self.store.all(self.tenant, "ascend_note_capture")):
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
            record.update(status="FAILED", verified=False, error_code="BRIDGE_CLAIM_TIMEOUT",
                          stage="claim", completed_at=now.isoformat())
            self.store.put(self.tenant, "ascend_note_capture", record["id"], record)
            self._audit("ASCEND_NOTE_READ_FAILED", "Unclaimed or unfinished note read-back timed out.",
                        {"write_id": record["id"], "load_id": record["load_id"],
                         "error_code": "BRIDGE_CLAIM_TIMEOUT"},
                        record.get("claimed_by") or record.get("actor_id") or "bridge")
            expired.append(record)
        return expired

    def _verify_outcome(self, verified: bool, private_present: bool, public_present: bool,
                        error_code: str | None) -> tuple[str, str | None]:
        observed = private_present or public_present
        if verified and observed:
            return "VERIFIED", None
        if verified and not observed:
            return "FAILED", "verify_without_presence"
        return "FAILED", error_code or "NOTE_CONTROLS_NOT_FOUND"

    def _require_demo(self):
        if Settings.from_env().mode != "demo":
            raise PermissionError("demo_mode_required")

    def _audit(self, event: str, explanation: str, facts: dict, actor_id: str) -> None:
        self.store.audit(AuditEvent(
            tenant_id=self.tenant,
            actor_id=actor_id,
            source="ascend_note_read",
            event=event,
            explanation=explanation,
            facts=facts,
            verified=event.endswith("VERIFIED"),
        ))
