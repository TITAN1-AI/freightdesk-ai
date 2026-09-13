import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, Field, SecretStr
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.runtime import RuntimePaths
from app.models.domain import AuditEvent, Model, utcnow
from app.services.store import Store
from integrations.carrierview.schemas import Position


class PositionPayload(Model):
    kind: Literal["new-position-sent"]
    position: Position


class StatusPayload(Model):
    kind: Literal["load-status-changed"]
    statuses: list | dict | str | None


class DriverMessagePayload(Model):
    kind: Literal["chat-message-created-by-driver"]
    message_id: str | None = None
    message: str = Field(max_length=10_000)


class LocalWebhookEvent(Model):
    """Local normalized contract, not an assertion of CarrierView's undocumented wire shape."""
    event_id: str | None = Field(default=None, max_length=200)
    provider_user_id: str
    provider_company_id: str
    provider_load_id: str
    occurred_at: AwareDatetime
    payload: Annotated[PositionPayload | StatusPayload | DriverMessagePayload, Field(discriminator="kind")]


class WebhookInbox:
    def __init__(self, store: Store, tenant: str, provider_user_id: str, provider_company_id: str):
        self.store, self.tenant = store, tenant
        self.user_id, self.company_id = provider_user_id, provider_company_id

    def receive(self, event: LocalWebhookEvent):
        if event.provider_user_id != self.user_id or event.provider_company_id != self.company_id:
            raise PermissionError("Webhook account association mismatch")
        raw = event.model_dump(mode="json")
        digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        event_key = event.event_id or digest
        source = "carrierview-webhook:" + event.payload.kind
        with self.store.transaction():
            binding = self.store.get(self.tenant, "carrierview_load_binding", event.provider_load_id)
            shipment_id = binding["shipment_id"]
            # Require actual tenant-scoped canonical association, not a body-supplied tenant/load number.
            self.store.get(self.tenant, "shipment", shipment_id)
            row = self.store.db.execute("SELECT digest FROM receipts WHERE tenant=? AND source=? AND id=?",
                (self.tenant, source, event_key)).fetchone()
            if row:
                if row[0] != digest:
                    raise ValueError("Webhook event ID reused with different content")
                return {"duplicate": True, "status": "PENDING_VERIFICATION"}
            self.store.db.execute("INSERT INTO receipts VALUES (?,?,?,?)", (self.tenant, source, event_key, digest))
            self.store.put(self.tenant, "webhook_inbox", source + ":" + event_key,
                {"shipment_id": shipment_id, "received_at": utcnow().isoformat(),
                 "occurred_at": event.occurred_at.isoformat(), "state": "PENDING_VERIFICATION",
                 "normalized_event": raw, "provider_authentication_verified": False})
            self.store.audit(AuditEvent(tenant_id=self.tenant, shipment_id=shipment_id,
                actor_id="local-webhook-ingress", source="carrierview", event="WEBHOOK_QUARANTINED",
                explanation="Local normalized event stored for verification; canonical facts unchanged",
                facts={"kind": event.payload.kind, "occurred_at": event.occurred_at.isoformat()},
                verified=False))
            return {"duplicate": False, "status": "PENDING_VERIFICATION"}


def create_webhook_app(*, local_test_key: SecretStr, tenant: str, provider_user_id: str,
                       provider_company_id: str, db_path=None):
    if len(local_test_key.get_secret_value()) < 32:
        raise ValueError("Local ingress key must contain at least 32 characters")

    @asynccontextmanager
    async def lifespan(app):
        store = Store(db_path or RuntimePaths.from_environment().path("Data", tenant, "carrierview.sqlite3"))
        app.state.inbox = WebhookInbox(store, tenant, provider_user_id, provider_company_id)
        try:
            yield
        finally:
            store.close()

    api = FastAPI(title="FreightDesk local webhook inbox", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @api.middleware("http")
    async def local_only(request: Request, next_handler):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            return JSONResponse({"detail": "Public ingress is not enabled"}, status_code=403)
        try:
            content_length = int(request.headers.get("content-length", "0") or "0")
        except ValueError:
            return JSONResponse({"detail": "Invalid content length"}, status_code=400)
        if content_length > 128_000:
            return JSONResponse({"detail": "Payload too large"}, status_code=413)
        # Bound the actual body as well, regardless of a missing/incorrect Content-Length.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 128_000:
                return JSONResponse({"detail": "Payload too large"}, status_code=413)
        request._body = bytes(body)
        response = await next_handler(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @api.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse({"detail": "Invalid local normalized webhook payload"}, status_code=422)

    @api.post("/webhooks/carrierview/{event_kind}")
    def receive(event_kind: str, event: LocalWebhookEvent, request: Request,
                x_freightdesk_ingress_key: str = Header(default="")):
        if not hmac.compare_digest(x_freightdesk_ingress_key.encode(), local_test_key.get_secret_value().encode()):
            raise HTTPException(401, "Local ingress authentication required")
        if event_kind != event.payload.kind:
            raise HTTPException(422, "Webhook kind mismatch")
        try:
            return request.app.state.inbox.receive(event)
        except PermissionError:
            raise HTTPException(403, "Webhook association denied") from None
        except KeyError:
            raise HTTPException(404, "Unknown webhook load association") from None
        except ValueError:
            raise HTTPException(409, "Webhook event conflict") from None

    return api
