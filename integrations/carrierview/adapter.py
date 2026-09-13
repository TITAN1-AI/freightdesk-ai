import time
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar
from urllib.parse import quote

import httpx
from pydantic import TypeAdapter, ValidationError

from app.models.domain import utcnow
from integrations.carrierview.config import CarrierViewConfig, CredentialClass
from integrations.carrierview.contract import ResponseContract
from integrations.carrierview.errors import (
    KNOWN_CODES, CarrierViewError, ContractMismatch, ScopeElevationRequired,
)
from integrations.carrierview.schemas import (
    CarrierViewLoad, CreateTrackingLoad, DriverChatMessage, DriverTextMessage, EditLoad,
    Position, Profile, ProviderEnvelope, WebhookConfiguration,
)

T = TypeVar("T")


@dataclass
class ReadResult(Generic[T]):
    data: T
    credential_class: CredentialClass
    received_at: Any
    duration_ms: float
    envelope: dict = field(repr=False)


class CarrierViewAdapter:
    """Documented endpoint transport. No redirects, proxies, credential fallback or retries.

    All real-network writes are intentionally disabled in this milestone. An explicit
    httpx.MockTransport exercises outbound request implementations offline.
    """

    def __init__(self, config: CarrierViewConfig, contract: ResponseContract,
                 audit: Callable[[dict], None], fixture_transport: httpx.MockTransport | None = None):
        if fixture_transport is not None and not isinstance(fixture_transport, httpx.MockTransport):
            raise TypeError("Only MockTransport is permitted for fixture injection")
        if config.credential_class == CredentialClass.TENANT and not config.elevation_reason:
            raise PermissionError("Tenant credential selection requires an explicit elevation reason")
        self.config, self.contract, self.audit = config, contract, audit
        self.fixture_mode = fixture_transport is not None
        self.client = httpx.AsyncClient(base_url=config.base_url, transport=fixture_transport,
            headers={"Authorization": "Bearer " + config.api_token.get_secret_value(),
                     "Content-Type": "application/json", "Accept": "application/json"},
            timeout=httpx.Timeout(config.timeout_seconds),
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=1),
            follow_redirects=False, trust_env=False)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    @staticmethod
    def provider_id(value: str | int) -> str:
        value = str(value)
        if not value or len(value) > 200 or any(c not in
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in value):
            raise ValueError("Invalid CarrierView provider identifier")
        return quote(value, safe="")

    def authorize_transport(self, method: str):
        if self.fixture_mode:
            return
        if method != "GET":
            raise PermissionError("Production CarrierView writes are disabled in this milestone")
        if not (self.config.origin_verified and self.config.network_reads_authorized
                and self.contract.verified_for_network):
            raise PermissionError("Owner read authorization, verified HTTPS origin and response contract required")

    async def _request(self, method, path, operation, body=None, params=None, action_id=None,
                       discovery=False):
        if not self.fixture_mode and self.config.credential_class == CredentialClass.AGENT:
            raise PermissionError("Agent credential is unavailable for API execution")
        if discovery:
            # Explicit owner-authorized envelope discovery, never typed mapping or import.
            exact_path = ("/api/loads/" + self.provider_id(self.config.discovery_provider_id)
                          if self.config.discovery_provider_id is not None else None)
            allowed = (
                (path == "/api/profile" and operation == "profile_discovery" and params is None)
                or (path == "/api/loads" and operation == "loads_discovery" and params == {"filter": "active"})
                or (path == "/api/loads" and operation == "past_loads_discovery" and params == {"filter": "past"})
                or (path == "/api/loads" and operation == "future_loads_discovery" and params == {"filter": "future"})
                or (exact_path is not None and params is None and (
                    (path == exact_path and operation == "exact_load_discovery")
                    or (path == exact_path + "/last-position" and operation == "exact_position_discovery")
                    or (path == exact_path + "/positions-history" and operation == "exact_history_discovery")
                ))
            )
            if method != "GET" or not allowed or body is not None or action_id is not None:
                raise PermissionError("Discovery is restricted to profile and authorized load-list GETs")
            if not self.fixture_mode and not (
                self.config.origin_verified and self.config.network_reads_authorized
                and self.config.discovery_reads_authorized
            ):
                raise PermissionError("Explicit owner discovery authorization and verified origin required")
        else:
            self.authorize_transport(method)
        started = time.perf_counter()
        common = {"operation": operation, "credential_class": self.config.credential_class.value,
                  "tenant_id": self.config.tenant_id, "external_action_id": action_id,
                  "elevated": self.config.credential_class == CredentialClass.TENANT,
                  "fixture": self.fixture_mode}
        # This audit precedes network dispatch. Failure to persist it fails closed.
        self.audit({**common, "event": "CARRIERVIEW_REQUEST_STARTED"})
        try:
            async with self.client.stream(method, path, json=body, params=params) as response:
                if response.status_code == 429:
                    header = response.headers.get("retry-after", "")
                    retry_after = min(3600, int(header)) if header.isdigit() else None
                    raise CarrierViewError("rate_limited", 429, retry_after_seconds=retry_after)
                if response.is_redirect:
                    raise CarrierViewError("redirect_rejected", response.status_code, uncertain=method != "GET")
                if response.status_code >= 500:
                    raise CarrierViewError("provider_server_error", response.status_code, uncertain=method != "GET")
                if response.status_code in {401, 403}:
                    raise ScopeElevationRequired("permission_denied", response.status_code)
                if not response.is_success:
                    raise CarrierViewError("http_error", response.status_code)
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > self.config.max_response_bytes:
                        raise ContractMismatch("response_too_large", response.status_code, uncertain=method != "GET")
                try:
                    envelope = ProviderEnvelope.model_validate_json(bytes(data))
                except ValidationError:
                    raise ContractMismatch("invalid_success_envelope", response.status_code,
                                           uncertain=method != "GET") from None
                raw = envelope.model_dump(exclude_unset=True)
                if envelope.success is not True:
                    code = envelope.error_code if envelope.error_code in KNOWN_CODES else "unknown_provider_error"
                    exception_type = ScopeElevationRequired if code == "permission_denied" else CarrierViewError
                    raise exception_type(code, response.status_code, errors=envelope.errors)
                duration = (time.perf_counter() - started) * 1000
                self.audit({**common, "event": "CARRIERVIEW_REQUEST_SUCCEEDED", "duration_ms": duration,
                            "http_status": response.status_code})
                return raw, duration
        except httpx.HTTPError:
            error = CarrierViewError("transport_error", uncertain=method != "GET")
            self.audit({**common, "event": "CARRIERVIEW_REQUEST_FAILED", **error.safe_result(),
                        "duration_ms": (time.perf_counter() - started) * 1000})
            raise error from None
        except CarrierViewError as error:
            self.audit({**common, "event": "CARRIERVIEW_REQUEST_FAILED", **error.safe_result(),
                        "duration_ms": (time.perf_counter() - started) * 1000})
            raise

    async def _read(self, path, capability, schema, params=None):
        if capability not in self.contract.selectors:
            raise ContractMismatch("response_selector_missing")
        raw, duration = await self._request("GET", path, capability, params=params)
        payload = self.contract.extract(capability, raw)
        try:
            data = TypeAdapter(schema).validate_python(payload)
        except ValidationError:
            raise ContractMismatch("typed_response_mismatch") from None
        return ReadResult(data, self.config.credential_class, utcnow(), duration, raw)

    async def get_profile(self) -> ReadResult[Profile]:
        return await self._read("/api/profile", "profile", Profile)

    async def get_integration_types(self) -> ReadResult[list | dict]:
        return await self._read("/api/loads/integration-types", "integration_types", list | dict)

    async def search_loads(self, filter: str = "active") -> ReadResult[list[CarrierViewLoad]]:
        if filter != "active":
            raise ValueError("Only the supplied active-load filter is verified for this milestone")
        return await self._read("/api/loads", "loads", list[CarrierViewLoad], {"filter": filter})

    async def get_load(self, provider_id: str) -> ReadResult[CarrierViewLoad]:
        result = await self._read("/api/loads/" + self.provider_id(provider_id), "load", CarrierViewLoad)
        if result.data.id is None or str(result.data.id) != str(provider_id):
            raise ContractMismatch("provider_load_identity_mismatch")
        return result

    async def get_last_position(self, provider_id: str) -> ReadResult[Position | None]:
        return await self._read("/api/loads/" + self.provider_id(provider_id) + "/last-position",
                                "last_position", Position | None)

    async def get_positions_history(self, provider_id: str, max_records: int = 50) -> ReadResult[list[Position]]:
        if not 1 <= max_records <= 100:
            raise ValueError("History must be bounded to 1–100 records")
        result = await self._read("/api/loads/" + self.provider_id(provider_id) + "/positions-history",
                                  "positions_history", list[Position])
        # No undocumented provider pagination/sort parameters. Preserve order; no claim of recency.
        result.data = result.data[:max_records]
        return result

    async def _write(self, action, method, path, body):
        # ActionLedger is the required internal boundary for every write.
        from app.services.action_ledger import ExternalAction, payload_hash
        if not isinstance(action, ExternalAction) or action.state != "IN_FLIGHT":
            raise PermissionError("Claimed action-ledger record required")
        if (action.tenant_id != self.config.tenant_id
                or action.credential_class != self.config.credential_class
                or action.request_method != method or action.request_path != path
                or action.payload_hash != payload_hash(body)):
            raise PermissionError("Action binding mismatch")
        raw, duration = await self._request(method, path, action.action_type, body,
                                             action_id=action.id)
        record = self.contract.created_record(raw) if action.action_type == "create_tracking_load" else raw
        return {"success": True, "duration_ms": duration, "credential_class": self.config.credential_class.value,
                "provider_id": record.get("id"), "fixture": self.fixture_mode,
                "tracking_number_url": record.get("tracking_number_url"), "client_url": record.get("client_url"),
                # Provider records remain in nonsynced ledger storage, never audit logs.
                "response": raw}

    async def create_tracking_load(self, action, payload: CreateTrackingLoad):
        self._check_action(action, "create_tracking_load", None)
        if self.contract.create_result_selector is None:
            raise PermissionError("Documented creation response selector required before dispatch")
        return await self._write(action, "POST", "/api/loads", payload.model_dump(exclude_none=True))

    async def edit_load(self, action, provider_id: str, payload: EditLoad):
        self._check_action(action, "edit_load", provider_id)
        return await self._write(action, "PATCH", "/api/loads/" + self.provider_id(provider_id),
                                 payload.model_dump(exclude_unset=True))

    async def disable_load(self, action, provider_id: str):
        self._check_action(action, "disable_load", provider_id)
        return await self._write(action, "PATCH", "/api/loads/" + self.provider_id(provider_id) + "/disable", {})

    async def send_driver_chat_message(self, action, provider_id: str, payload: DriverChatMessage):
        self._check_action(action, "send_driver_chat_message", provider_id)
        return await self._write(action, "POST", "/api/loads/" + self.provider_id(provider_id) + "/chat-message",
                                 payload.model_dump(exclude_unset=True))

    async def send_driver_text_message(self, action, provider_id: str, payload: DriverTextMessage):
        self._check_action(action, "send_driver_text_message", provider_id)
        return await self._write(action, "POST", "/api/loads/" + self.provider_id(provider_id) + "/text-message",
                                 payload.model_dump(exclude_unset=True))

    async def configure_webhooks(self, action, payload: WebhookConfiguration):
        self._check_action(action, "configure_webhooks", None)
        return await self._write(action, "PUT", "/api/webhook/" + payload.event, {"url": payload.url})

    @staticmethod
    def _check_action(action, action_type, provider_id):
        if action.action_type != action_type or action.provider_load_id != provider_id:
            raise PermissionError("Action type / provider load mismatch")

    async def get_documents(self, provider_id: str):
        from integrations.interfaces import CapabilityUnavailable
        raise CapabilityUnavailable("CarrierView documents/POD API is not established by the supplied contract")
