"""Local demo routes for the portable browser bridge. Extension CORS only on this prefix."""

from __future__ import annotations

import re

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import Field

from app.models.domain import Model
from app.services.portable_leases import (
    ALLOWED_ORIGIN,
    DEFAULT_LEASE_TTL_SECONDS,
    HARVEST_SCOPE,
    MAX_LEASE_TTL_SECONDS,
    MIN_LEASE_TTL_SECONDS,
    PortableLeaseService,
)

PORTABLE_PATH_PREFIX = "/v1/portable"
EXTENSION_ORIGIN = re.compile(r"^chrome-extension://[a-p]{32}$")
PORTABLE_HEADER = "x-freightdesk-portable"


class SessionBody(Model):
    placeholder: bool = True


class LeaseCreateBody(Model):
    origin: str = Field(default=ALLOWED_ORIGIN, min_length=8, max_length=64)
    scope: str = Field(default=HARVEST_SCOPE, min_length=8, max_length=64)
    ttl_seconds: int = Field(default=DEFAULT_LEASE_TTL_SECONDS, ge=MIN_LEASE_TTL_SECONDS,
                             le=MAX_LEASE_TTL_SECONDS)


class HarvestBody(Model):
    lease_id: str = Field(min_length=8, max_length=64)
    origin: str = Field(min_length=8, max_length=64)
    view: str = Field(min_length=4, max_length=32)
    view_confidence: str = Field(min_length=4, max_length=32)
    coverage: str = Field(min_length=8, max_length=64)
    evidence_class: str = Field(min_length=4, max_length=32)
    live_validated: bool
    values_included: bool
    production_writes: bool
    revision: str = Field(min_length=64, max_length=64)
    captured_at: str = Field(min_length=8, max_length=64)
    row_count: int = Field(ge=0, le=100)
    rows: list[dict] = Field(default_factory=list)


def portable_origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True
    return EXTENSION_ORIGIN.fullmatch(origin) is not None


def portable_cors_origin(origin: str | None) -> str | None:
    if origin and EXTENSION_ORIGIN.fullmatch(origin):
        return origin
    return None


def apply_portable_cors(response: Response, origin: str | None) -> Response:
    allowed = portable_cors_origin(origin)
    if allowed:
        response.headers["Access-Control-Allow-Origin"] = allowed
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-FreightDesk-Portable"
        response.headers["Access-Control-Max-Age"] = "600"
        response.headers["Vary"] = "Origin"
    return response


def portable_preflight(origin: str | None) -> Response:
    if origin and not portable_origin_allowed(origin):
        return JSONResponse({"detail": "Cross-origin access denied"}, status_code=403)
    response = Response(status_code=204)
    return apply_portable_cors(response, origin)


def bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 7:
        return auth[7:]
    return None


def install_portable_routes(api):
    def service(request: Request) -> PortableLeaseService:
        return request.app.state.portable

    @api.get(f"{PORTABLE_PATH_PREFIX}/status")
    def status(request: Request):
        token = bearer_token(request)
        try:
            return service(request).status(token)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from None

    @api.post(f"{PORTABLE_PATH_PREFIX}/session")
    def session(body: SessionBody, request: Request):
        if request.headers.get(PORTABLE_HEADER) != "1":
            raise HTTPException(status_code=403, detail="Portable demo header required")
        if body.placeholder is not True:
            raise HTTPException(status_code=409, detail="placeholder_auth_required")
        return service(request).create_device_session()

    @api.post(f"{PORTABLE_PATH_PREFIX}/leases")
    def create_lease(body: LeaseCreateBody, request: Request):
        token = bearer_token(request)
        if not token:
            raise HTTPException(status_code=401, detail="device_session_required")
        try:
            return service(request).create_lease(token, body.origin, body.scope, body.ttl_seconds)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from None

    @api.post(f"{PORTABLE_PATH_PREFIX}/leases/{{lease_id}}/revoke")
    def revoke_lease(lease_id: str, request: Request):
        token = bearer_token(request)
        if not token:
            raise HTTPException(status_code=401, detail="device_session_required")
        try:
            return service(request).revoke_lease(token, lease_id)
        except PermissionError as exc:
            code = 401 if str(exc) == "device_session_required" else 403
            raise HTTPException(status_code=code, detail=str(exc)) from None

    @api.post(f"{PORTABLE_PATH_PREFIX}/harvest")
    def harvest(body: HarvestBody, request: Request):
        token = bearer_token(request)
        if not token:
            raise HTTPException(status_code=401, detail="lease_required")
        try:
            return service(request).accept_harvest(token, body.model_dump())
        except PermissionError as exc:
            code = 401 if str(exc) == "lease_required" else 403
            raise HTTPException(status_code=code, detail=str(exc)) from None
