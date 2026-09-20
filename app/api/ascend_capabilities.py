"""Capability map and write stubs for the portable Ascend facade."""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from app.api.ascend_facade import make_facade_reader
from app.models.domain import Model
from app.services.ascend_capabilities import AscendCapabilityService


class StatusChangeBody(Model):
    status: str = Field(min_length=1, max_length=32)
    approval_token: str | None = Field(default=None, max_length=200)


class ForbiddenWriteBody(Model):
    approval_token: str | None = Field(default=None, max_length=200)


def install_ascend_capability_routes(api, identity):
    facade_reader = make_facade_reader(identity)

    def capabilities(request: Request) -> AscendCapabilityService:
        return request.app.state.capabilities

    @api.get("/v1/ascend/capabilities")
    def ascend_capability_map(request: Request, _actor=Depends(facade_reader)):
        """Machine-readable READ/WRITE/AUTOMATION map. Not a retail Ascend API."""
        return capabilities(request).catalog()

    @api.get("/v1/ascend/loads/{load_id}")
    def ascend_facade_load(load_id: str, request: Request, _actor=Depends(facade_reader)):
        """Last known CANDIDATE fields for one harvested load. Empty-safe when missing."""
        return capabilities(request).facade_load(load_id)

    @api.post("/v1/ascend/loads/{load_id}/status")
    def change_load_status(load_id: str, body: StatusChangeBody, request: Request,
                           actor=Depends(facade_reader)):
        """Queue a load-status change. APPROVAL_REQUIRED. Not LIVE_VALIDATED."""
        code, receipt = request.app.state.status.change_status(
            actor.id, load_id, body.status, body.approval_token)
        return JSONResponse(receipt, status_code=code)

    @api.post("/v1/ascend/loads/{load_id}/assign")
    def ascend_assign_stub(load_id: str, body: ForbiddenWriteBody, request: Request,
                           _actor=Depends(facade_reader)):
        """Assign carrier stays FORBIDDEN on this track."""
        code, receipt = capabilities(request).refuse_write(
            load_id, "assign_carrier", {"approval_present": bool(body.approval_token)})
        return JSONResponse(receipt, status_code=code)

    @api.post("/v1/ascend/loads/{load_id}/expenses")
    def ascend_expenses_stub(load_id: str, body: ForbiddenWriteBody, request: Request,
                             _actor=Depends(facade_reader)):
        """Expense / money writes stay FORBIDDEN on this track."""
        code, receipt = capabilities(request).refuse_write(
            load_id, "write_expenses", {"approval_present": bool(body.approval_token)})
        return JSONResponse(receipt, status_code=code)
