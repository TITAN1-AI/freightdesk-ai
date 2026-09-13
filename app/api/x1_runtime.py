"""Explicit local owner controls; demo sessions and provider pages cannot grant read access."""

from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


class RuntimeControl(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["enable", "disable", "pause", "resume", "rebind", "repair"]
    hours: int = Field(default=8, ge=1, le=8)


def runtime_access():
    from executors.ascend_extension.pairing import PairingRepository
    from executors.ascend_extension.runtime import RuntimeAccess

    return RuntimeAccess(PairingRepository())


def revoke_enrollment():
    from executors.ascend_extension.enrollment import EnrollmentRepository
    from executors.ascend_extension.pairing import PairingRepository

    EnrollmentRepository(PairingRepository()).revoke(owner_authorized=True)


def install_routes(api, owner_boundary):
    def boundary(request):
        owner_boundary(request)
        if request.method != "GET" and request.headers.get("x-freightdesk-local") != "1":
            raise HTTPException(403, "Explicit local owner action required")

    @api.get("/api/ascend/runtime/status")
    def status(request: Request):
        boundary(request)
        try:
            return runtime_access().status()
        except Exception:
            # Do not let configuration/DPAPI/SQLite exceptions cross the local HTTP boundary.
            return {"state": "ERROR", "owner_action": "Check the local Ascend enrollment.",
                    "production_writes": False, "read_access": "DISABLED"}

    @api.post("/api/ascend/runtime/control")
    def control(body: RuntimeControl, request: Request):
        boundary(request)
        try:
            access = runtime_access()
            if body.action == "enable":
                access.enable(owner_authorized=True, hours=body.hours)
            elif body.action == "disable":
                access.disable(owner_authorized=True)
            elif body.action in {"pause", "resume"}:
                access.set_paused(body.action == "pause", owner_authorized=True)
            elif body.action == "rebind":
                access.request_rebind(owner_authorized=True)
            else:
                # This only closes access. Creating/importing a new enrollment remains a local
                # owner action, never something an HTTP request can silently carry out.
                access.disable(owner_authorized=True)
                revoke_enrollment()
            return access.status()
        except Exception:
            raise HTTPException(409, "Read access unchanged or closed. Check enrollment and owner access.") from None
