"""Demo agent API session routes. Bearer auth for Avery; not cloud OAuth."""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.api.portable_leases import bearer_token
from app.services.portable_leases import PortableLeaseService

AGENT_PATH_PREFIX = "/v1/agent"


def install_agent_routes(api):
    def service(request: Request) -> PortableLeaseService:
        return request.app.state.portable

    @api.get(f"{AGENT_PATH_PREFIX}/status")
    def agent_status(request: Request):
        token = bearer_token(request)
        try:
            return service(request).agents.public_status(token)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from None

    @api.post(f"{AGENT_PATH_PREFIX}/session")
    def create_agent_session(request: Request):
        try:
            return service(request).agents.create_or_get()
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None

    @api.get(f"{AGENT_PATH_PREFIX}/session")
    def read_agent_session(request: Request):
        token = bearer_token(request)
        if not token:
            raise HTTPException(status_code=401, detail="agent_session_required")
        try:
            return service(request).agents.public_status(token)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from None
