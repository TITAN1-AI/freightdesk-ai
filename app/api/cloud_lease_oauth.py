"""Additive OAuth / device-code routes on the portable prefix. Demo sign-in stays."""

from __future__ import annotations

from fastapi import HTTPException, Request
from pydantic import Field

from app.api.portable_leases import PORTABLE_HEADER, PORTABLE_PATH_PREFIX
from app.models.domain import Model
from app.services.cloud_lease_oauth import DEVICE_GRANT, CloudLeaseOAuthService

OAUTH_PREFIX = f"{PORTABLE_PATH_PREFIX}/oauth"


class DevicePollBody(Model):
    device_code: str = Field(min_length=16, max_length=128)
    grant_type: str = Field(default=DEVICE_GRANT, min_length=8, max_length=80)


class TokenBody(Model):
    grant_type: str = Field(min_length=8, max_length=80)
    device_code: str | None = Field(default=None, max_length=128)
    code: str | None = Field(default=None, max_length=128)
    code_verifier: str | None = Field(default=None, max_length=128)
    redirect_uri: str | None = Field(default=None, max_length=2048)


class AuthorizeBody(Model):
    response_type: str = Field(default="code", min_length=4, max_length=16)
    code_challenge: str = Field(min_length=32, max_length=128)
    code_challenge_method: str = Field(default="S256", min_length=4, max_length=8)
    redirect_uri: str = Field(min_length=12, max_length=2048)


def _require_portable_header(request: Request) -> None:
    if request.headers.get(PORTABLE_HEADER) != "1":
        raise HTTPException(status_code=403, detail="Portable demo header required")


def install_cloud_lease_oauth_routes(api):
    def service(request: Request) -> CloudLeaseOAuthService:
        return request.app.state.cloud_lease

    @api.get(OAUTH_PREFIX)
    def catalog(request: Request):
        return service(request).catalog()

    @api.get(f"{OAUTH_PREFIX}/device/verify")
    def verify(request: Request):
        return service(request).verify_page()

    @api.post(f"{OAUTH_PREFIX}/device/start")
    def start_device(request: Request):
        _require_portable_header(request)
        return service(request).start_device_authorization()

    @api.post(f"{OAUTH_PREFIX}/device/poll")
    def poll_device(body: DevicePollBody, request: Request):
        _require_portable_header(request)
        return service(request).poll_device(body.device_code, body.grant_type)

    @api.post(f"{OAUTH_PREFIX}/token")
    def token(body: TokenBody, request: Request):
        _require_portable_header(request)
        return service(request).exchange_token(body.grant_type, body.device_code, body.code)

    @api.post(f"{OAUTH_PREFIX}/authorize")
    def authorize(body: AuthorizeBody, request: Request):
        _require_portable_header(request)
        if body.response_type != "code" or body.code_challenge_method != "S256":
            raise HTTPException(status_code=409, detail="unsupported_authorize")
        service(request).refuse_authorize()

    @api.post(f"{OAUTH_PREFIX}/revoke")
    def revoke_cloud(request: Request):
        _require_portable_header(request)
        service(request).refuse_revoke_cloud_token()
