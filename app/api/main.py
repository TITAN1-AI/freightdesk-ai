import asyncio
import hmac
import os
import secrets
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.agent_sessions import install_agent_routes
from app.api.ascend_facade import install_ascend_facade_routes
from app.api.portable_leases import (
    PORTABLE_PATH_PREFIX,
    apply_portable_cors,
    install_portable_routes,
    portable_origin_allowed,
    portable_preflight,
)
from app.services.agent_sessions import AgentSessionService
from app.core.config import ROOT, Settings
from app.core.runtime import RuntimePaths
from app.models.domain import ActionPolicy, AuthorizedIdentity, ExternalEvent, Model, Role
from app.scheduler.worker import scheduler_loop
from app.services.control_plane import ControlPlane
from app.services.portable_leases import PortableLeaseService
from app.services.store import Store
from app.services.carrierview_poc import live_projection
from app.services.live_access import redeem_grant, session_valid


class CommandBody(Model):
    command: str = Field(min_length=1, max_length=300)


class ActionBody(Model):
    shipment_id: str = Field(max_length=100)
    action: Literal["routine_customer_update"]
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9:_-]+$")


class DecisionBody(Model):
    decision: Literal["APPROVED", "REJECTED"]


class PauseBody(Model):
    paused: bool
    shipment_id: str | None = None
    takeover: bool = False


class LiveGrantBody(Model):
    grant: str = Field(min_length=32, max_length=128, repr=False)


class PolicyBody(Model):
    action: str = Field(max_length=100)
    policy: ActionPolicy


def local_token():
    token = os.getenv("FREIGHTDESK_OWNER_TOKEN", "")
    if token:
        if len(token) < 32:
            raise ValueError("Local owner token must contain at least 32 characters")
        return token
    path = RuntimePaths.from_environment().path("Tokens", "demo-owner-token.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


def create_app(db_path: Path | None = None, token: str | None = None, run_scheduler: bool = True,
               agent_bootstrap_path: Path | None = None):
    settings = Settings.from_env()
    owner_token = token or local_token()
    session_token = secrets.token_urlsafe(48)
    database_path = db_path or RuntimePaths.from_environment().path("Data", settings.tenant, "demo.sqlite3")

    @asynccontextmanager
    async def lifespan(application):
        store = Store(database_path)
        bootstrap = agent_bootstrap_path
        if bootstrap is None and db_path is None:
            try:
                bootstrap = RuntimePaths.from_environment().path("Tokens", "demo-agent-token.txt")
            except ValueError:
                bootstrap = None
        agents = AgentSessionService(store, settings.tenant, bootstrap_path=bootstrap)
        application.state.control = ControlPlane(store, settings)
        application.state.portable = PortableLeaseService(store, settings.tenant, agents=agents)
        worker = asyncio.create_task(scheduler_loop(application.state.control)) if run_scheduler else None
        from app.api.ascend_mapping import mapping_loop
        mapping_worker = asyncio.create_task(mapping_loop()) if run_scheduler else None
        try:
            yield
        finally:
            if worker:
                worker.cancel()
                with suppress(asyncio.CancelledError):
                    await worker
            if mapping_worker:
                mapping_worker.cancel()
                with suppress(asyncio.CancelledError):
                    await mapping_worker
            store.close()

    api = FastAPI(title="FreightDesk AI", version="0.1.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @api.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            return JSONResponse({"detail": "Local access only"}, status_code=403)
        origin = request.headers.get("origin")
        portable = request.url.path.startswith(PORTABLE_PATH_PREFIX)
        if portable:
            if not portable_origin_allowed(origin):
                return JSONResponse({"detail": "Cross-origin access denied"}, status_code=403)
            if request.method == "OPTIONS":
                return portable_preflight(origin)
        else:
            expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
            if origin and origin != expected:
                return JSONResponse({"detail": "Cross-origin access denied"}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Cross-site access denied"}, status_code=403)
        response = await call_next(request)
        if portable:
            apply_portable_cors(response, origin)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    def control(request: Request):
        return request.app.state.control

    def identity(request: Request):
        auth = request.headers.get("authorization", "")
        bearer = auth[7:] if auth.startswith("Bearer ") else ""
        cookie = request.cookies.get("freightdesk_session", "")
        if not (hmac.compare_digest(bearer, owner_token) or hmac.compare_digest(cookie, session_token)):
            raise HTTPException(status_code=401, detail="Local session required")
        if request.method not in {"GET", "HEAD"} and not bearer:
            if request.headers.get("x-freightdesk-local") != "1":
                raise HTTPException(status_code=403, detail="Local request header required")
        return AuthorizedIdentity(id="local-owner", tenant_id=settings.tenant, role=Role.OWNER)

    @api.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @api.exception_handler(PermissionError)
    async def forbidden(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @api.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Record not found"}, status_code=404)

    @api.get("/healthz")
    def health():
        return {"status": "ok", "mode": "demo", "live_validated": False}

    @api.post("/api/session")
    def session(request: Request):
        # Demo-only local workstation trust. Custom header cannot be sent cross-origin without
        # a preflight; no CORS permissions exist. Never enable this bootstrap for live deployment.
        if request.headers.get("x-freightdesk-local") != "1":
            raise HTTPException(status_code=403, detail="Local request header required")
        response = JSONResponse({"role": "OWNER", "mode": "demo"})
        response.set_cookie("freightdesk_session", session_token, httponly=True, samesite="strict",
                            max_age=28800, path="/")
        return response

    @api.get("/api/snapshot")
    def snapshot(actor=Depends(identity), plane=Depends(control)):
        return plane.snapshot(actor)

    @api.get("/api/carrierview/poc")
    def carrierview_poc(request: Request):
        # Demo bootstrap cookies never authorize live data. This separate local read view
        # requires an explicitly configured owner secret, kept out of browser persistence.
        live_token = os.getenv("FREIGHTDESK_LIVE_VIEW_TOKEN", "")
        live_cookie = request.cookies.get("freightdesk_live_session", "")
        if len(live_token) < 32 and not live_cookie:
            raise HTTPException(403, "Live POC view is locked; dedicated owner access is not configured")
        auth = request.headers.get("authorization", "")
        supplied = auth[7:] if auth.startswith("Bearer ") else ""
        bearer_valid = len(live_token) >= 32 and hmac.compare_digest(supplied.encode(), live_token.encode())
        path = RuntimePaths.from_environment().path("Data", settings.tenant, "carrierview.sqlite3")
        if not path.exists():
            return {"imported": False, "live_validated": False, "shipment": None}
        store = Store(path)
        try:
            with store.transaction():
                if not bearer_valid and not session_valid(store, settings.tenant, live_cookie):
                    raise HTTPException(401, "Dedicated live-view owner session required")
                return live_projection(store, settings.tenant)
        finally:
            store.close()

    @api.post("/api/carrierview/live-session")
    def live_session(body: LiveGrantBody):
        path = RuntimePaths.from_environment().path("Data", settings.tenant, "carrierview.sqlite3")
        if not path.exists():
            raise HTTPException(403, "Verified POC has not been imported")
        store = Store(path)
        try:
            try:
                session = redeem_grant(store, settings.tenant, body.grant)
            except (KeyError, PermissionError):
                raise HTTPException(401, "Owner launch link expired or invalid") from None
        finally:
            store.close()
        response = JSONResponse({"historical_view": True})
        response.set_cookie("freightdesk_live_session", session, httponly=True, samesite="strict",
                            max_age=28800, path="/api")
        return response

    @api.get("/api/mail/status")
    def mail_status():
        from integrations.outlook.config import MicrosoftConfig
        configured = MicrosoftConfig.config_path().exists()
        return {"configured": configured, "live_validated": False,
                "status": "Awaiting owner authentication" if configured else "Awaiting Entra registration",
                "sending": "Disabled · APPROVAL_REQUIRED", "mode": "Read + unsent drafts foundation"}

    @api.get("/api/ascend/status")
    def ascend_status():
        return {"status":"Offline foundation · awaiting owner live authorization", "live_validated":False,
                "production_writes":"BLOCKED", "executor_status":"No automatic browser launch"}

    @api.get("/api/ascend/summary")
    def ascend_summary(request: Request):
        # The dedicated owner grant/cookie is required; demo bootstrap never exposes provider facts.
        path = RuntimePaths.from_environment().path("Data", settings.tenant, "carrierview.sqlite3")
        if not path.exists():
            raise HTTPException(403, "Dedicated owner session required")
        carrierview_poc(request)
        from app.services.ascend_live import projected_summary
        return projected_summary()

    def x1_owner_boundary(request: Request):
        if settings.tenant != "booking-logistics":
            raise HTTPException(403, "Booking Logistics owner session required")
        # The protected live-owner identity is separate from the open demo bootstrap. An explicit
        # owner control changes local read authorization only; it never authorizes vendor writes.
        path = RuntimePaths.from_environment().path("Data", settings.tenant, "carrierview.sqlite3")
        if not path.exists():
            raise HTTPException(403, "Dedicated owner session required")
        from app.services.live_access import session_valid_readonly
        token = os.getenv("FREIGHTDESK_LIVE_VIEW_TOKEN", "")
        auth = request.headers.get("authorization", "")
        bearer = auth[7:] if auth.startswith("Bearer ") else ""
        bearer_valid = len(token) >= 32 and hmac.compare_digest(bearer.encode(), token.encode())
        if not bearer_valid and not session_valid_readonly(
            path, settings.tenant, request.cookies.get("freightdesk_live_session", "")
        ):
            raise HTTPException(401, "Dedicated owner session required")

    from app.api.x1_runtime import install_routes as install_x1_runtime_routes
    install_x1_runtime_routes(api, x1_owner_boundary)
    from app.api.ascend_mapping import install_routes as install_mapping_routes
    install_mapping_routes(api, x1_owner_boundary)
    install_portable_routes(api)
    install_agent_routes(api)
    install_ascend_facade_routes(api, identity)

    @api.get("/api/mail/summary")
    @api.get("/api/mail/shipments/{shipment_id}")
    def mailbox_summary(request: Request, shipment_id: str | None = None):
        # Reuse the dedicated owner boundary; demo bootstrap never authorizes mailbox records.
        owner_store = RuntimePaths.from_environment().path("Data", settings.tenant, "carrierview.sqlite3")
        if not owner_store.exists():
            raise HTTPException(403, "Dedicated owner session required")
        carrierview_poc(request)
        from app.services.mail_view import mail_summary
        path = RuntimePaths.from_environment().path("Data", settings.tenant, "mail.sqlite3")
        store = Store(path)
        try:
            return mail_summary(store, settings.tenant, shipment_id)
        finally:
            store.close()

    @api.get("/api/shipments/{shipment_id}")
    def shipment(shipment_id: str, actor=Depends(identity), plane=Depends(control)):
        return next((s for s in plane.snapshot(actor)["shipments"] if s["id"] == shipment_id), None) or (
            _not_found()
        )

    @api.post("/api/commands")
    def command(body: CommandBody, actor=Depends(identity), plane=Depends(control)):
        return plane.command(actor, body.command)

    @api.post("/api/events")
    def event(body: ExternalEvent, actor=Depends(identity), plane=Depends(control)):
        # Local owner event input only. This endpoint is NOT a public vendor webhook.
        if body.source != "dashboard":
            raise HTTPException(status_code=422, detail="Only dashboard events are accepted here")
        return plane.process_event(actor, body)

    @api.post("/api/actions")
    def action(body: ActionBody, actor=Depends(identity), plane=Depends(control)):
        return plane.request_action(actor, body.shipment_id, body.action, body.request_id)

    @api.post("/api/approvals/{approval_id}")
    def decide(approval_id: str, body: DecisionBody, actor=Depends(identity), plane=Depends(control)):
        return plane.decide(actor, approval_id, body.decision)

    @api.post("/api/pause")
    def pause(body: PauseBody, actor=Depends(identity), plane=Depends(control)):
        return plane.set_pause(actor, body.paused, body.shipment_id, body.takeover)

    @api.post("/api/policies")
    def policies(body: PolicyBody, actor=Depends(identity), plane=Depends(control)):
        return plane.update_policy(actor, body.action, body.policy)

    api.mount("/assets", StaticFiles(directory=ROOT / "app/dashboard"), name="assets")

    @api.get("/")
    def dashboard():
        return FileResponse(ROOT / "app/dashboard/index.html")

    return api


def _not_found():
    raise HTTPException(status_code=404, detail="Shipment not found")
