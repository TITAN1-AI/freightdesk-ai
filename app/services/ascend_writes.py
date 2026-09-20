"""Shared mint/claim/complete dispatcher for portable Ascend writes."""

from __future__ import annotations

from app.models.domain import utcnow
from app.services.ascend_notes import NOTE_ACTION, NOTE_ACTION_VIA_SAVE
from app.services.ascend_status import STATUS_ACTION, STATUS_ACTION_VIA_SAVE


class AscendWriteBroker:
    def __init__(self, notes, status):
        self.notes = notes
        self.status = status

    def mint_approval(self, actor_id: str, action: str, load_id: str, text: str | None = None,
                      status: str | None = None, allow_whole_form_save: bool = False) -> dict:
        if action in {NOTE_ACTION, NOTE_ACTION_VIA_SAVE}:
            return self.notes.mint_approval(actor_id, action, load_id, text, allow_whole_form_save)
        if action in {STATUS_ACTION, STATUS_ACTION_VIA_SAVE}:
            return self.status.mint_approval(actor_id, action, load_id, status, allow_whole_form_save)
        raise ValueError("approval_action_unsupported")

    def get_write(self, write_id: str) -> dict:
        if self.notes.has_write(write_id):
            return self.notes.get_write(write_id)
        return self.status.get_write(write_id)

    def claim_pending(self, token: str) -> dict:
        principal = self.notes.portable._require_principal(token)
        now = utcnow()
        notes_expired = self.notes.expire_stale(now)
        status_expired = self.status.expire_stale(now)
        candidates = [("note", item) for item in self.notes.claimable(principal["id"])]
        candidates.extend(("status", item) for item in self.status.claimable(principal["id"]))
        if not candidates:
            timed_out = (notes_expired + status_expired)[0] if (notes_expired or status_expired) else None
            empty = {"pending": False, "live_validated": False, "stage": "claim_wait"}
            if timed_out:
                empty.update(write_id=timed_out["id"], error_code="BRIDGE_CLAIM_TIMEOUT",
                             stage="claim", status="FAILED",
                             action=timed_out.get("action"))
            return empty
        kind, record = min(candidates, key=lambda item: item[1]["created_at"])
        if kind == "note":
            return self.notes.claim_record(record, principal, now)
        return self.status.claim_record(record, principal, now)

    def complete(self, token: str, write_id: str, verified: bool, note_present: bool,
                 error_code: str | None, live_validated: bool, production_writes: bool,
                 stage: str | None = None, opener_strategy: str | None = None,
                 note_label: str | None = None, commit_kind: str | None = None,
                 save_variant: str | None = None, tab_hint: str | None = None,
                 reopen_attempts: int | None = None, verify_reason: str | None = None,
                 bridge_version: str | None = None, status_matched: bool = False,
                 observed_status: str | None = None) -> dict:
        if self.status.has_write(write_id):
            return self.status.complete(
                token, write_id, verified, status_matched, observed_status, error_code,
                live_validated, production_writes, stage, opener_strategy, commit_kind,
                save_variant, tab_hint, reopen_attempts, verify_reason, bridge_version)
        return self.notes.complete(
            token, write_id, verified, note_present, error_code, live_validated,
            production_writes, stage, opener_strategy, note_label, commit_kind,
            save_variant, tab_hint, reopen_attempts, verify_reason, bridge_version)
