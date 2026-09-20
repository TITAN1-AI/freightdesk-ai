"""HTTP facade for demo Ascend private-internal-note writes. Not LIVE_VALIDATED."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.ascend_facade import make_facade_reader
from app.api.portable_leases import bearer_token
from app.models.domain import AuthorizedIdentity
from app.services.ascend_notes import ApprovalMintBody, NoteWriteBody, WriteCompleteBody


def install_ascend_note_routes(api, identity):
    facade_reader = make_facade_reader(identity)

    def notes(request: Request):
        return request.app.state.notes

    @api.post("/v1/ascend/approvals")
    def mint_note_approval(body: ApprovalMintBody, request: Request,
                           actor: AuthorizedIdentity = Depends(facade_reader)):
        """Mint a one-use demo approval for ASCEND_ADD_INTERNAL_NOTE.

        Default ActionPolicy is APPROVAL_REQUIRED. The dashboard button posts here too.
        """
        return notes(request).mint_approval(
            actor.id, body.action, body.load_id, body.text, body.allow_whole_form_save)

    @api.post("/v1/ascend/loads/{load_id}/notes")
    def add_internal_note(load_id: str, body: NoteWriteBody, request: Request,
                          actor: AuthorizedIdentity = Depends(facade_reader)):
        """Queue a private/internal note. Rejects without a valid approval by default."""
        code, receipt = notes(request).add_note(actor.id, load_id, body.text, body.approval_token)
        return JSONResponse(receipt, status_code=code)

    @api.get("/v1/ascend/writes/{write_id}")
    def read_note_write(write_id: str, request: Request, _actor=Depends(facade_reader)):
        return notes(request).get_write(write_id)

    @api.get("/v1/portable/writes/pending")
    def claim_pending_note_write(request: Request):
        token = bearer_token(request)
        if not token:
            raise HTTPException(status_code=401, detail="device_session_required")
        return notes(request).claim_pending(token)

    @api.post("/v1/portable/writes/{write_id}/complete")
    def complete_note_write(write_id: str, body: WriteCompleteBody, request: Request):
        token = bearer_token(request)
        if not token:
            raise HTTPException(status_code=401, detail="device_session_required")
        return notes(request).complete(
            token, write_id, body.verified, body.note_present, body.error_code,
            body.live_validated, body.production_writes, body.stage, body.opener_strategy,
            body.note_label, body.commit_kind, body.save_variant, body.tab_hint,
            body.reopen_attempts, body.verify_reason, body.bridge_version)
