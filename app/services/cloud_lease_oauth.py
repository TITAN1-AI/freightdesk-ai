"""Cloud lease OAuth / device-code contract. Demo rehearsal. Does not mint sessions."""

from __future__ import annotations

import hmac
import json
import secrets
from datetime import timedelta

from app.core.config import ROOT, Settings
from app.models.domain import AuditEvent, utcnow
from app.services.auth_tokens import token_digest

OAUTH_CONFIG = ROOT / "config" / "cloud-lease-oauth-v0.json"
CLOUD_IDP = "NOT_CONFIGURED"
DEVICE_KIND = "portable_oauth_device"
DEVICE_TTL = timedelta(minutes=15)
POLL_INTERVAL_SECONDS = 5
MAX_PENDING = 8
USER_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ23456789"
DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
VERIFY_PATH = "/v1/portable/oauth/device/verify"
DEMO_API = "http://127.0.0.1:8787"


def load_oauth_config() -> dict:
    return json.loads(OAUTH_CONFIG.read_text(encoding="utf-8"))


class CloudLeaseOAuthService:
    def __init__(self, store, tenant: str):
        self.store = store
        self.tenant = tenant

    def catalog(self) -> dict:
        self._require_demo()
        contract = load_oauth_config()
        return {
            "mode": "demo",
            "product": "portable-bridge",
            "track": "B",
            "cloud_idp": CLOUD_IDP,
            "live_validated": False,
            "production_writes": False,
            "mints_session_from_oauth": False,
            "replaces_placeholder": False,
            "demo_sign_in_unchanged": True,
            "placeholder_session": {
                "implemented": True,
                "route": "POST /v1/portable/session",
                "auth_kind": "PLACEHOLDER",
            },
            "agent_bearer": {
                "implemented": True,
                "route": "POST /v1/agent/session",
                "auth_kind": "DEMO_AGENT",
                "not_oauth": True,
            },
            "device_code": {
                "implemented": "rehearsal",
                "mints_session": False,
                "start": "POST /v1/portable/oauth/device/start",
                "poll": "POST /v1/portable/oauth/device/poll",
                "grant_type": DEVICE_GRANT,
            },
            "authorization_code_pkce": {
                "implemented": False,
                "mints_session": False,
                "code_challenge_method": "S256",
            },
            "after_auth": contract["after_auth"],
            "auth_modes": contract["auth_modes"],
        }

    def start_device_authorization(self) -> dict:
        self._require_demo()
        device_code = secrets.token_urlsafe(32)
        user_code = self._user_code()
        now = utcnow()
        expires = now + DEVICE_TTL
        with self.store.transaction():
            pending = [item for item in self._pending()
                       if item["status"] == "PENDING" and item["expires_at"] > now.isoformat()]
            if len(pending) >= MAX_PENDING:
                raise ValueError("device_authorization_bound")
            record = {
                "id": token_digest(device_code)[:32],
                "device_code_digest": token_digest(device_code),
                "user_code": user_code,
                "status": "PENDING",
                "created_at": now.isoformat(),
                "expires_at": expires.isoformat(),
                "cloud_idp": CLOUD_IDP,
                "mints_session": False,
            }
            self.store.put(self.tenant, DEVICE_KIND, record["id"], record)
            self._audit("PORTABLE_OAUTH_DEVICE_STARTED",
                        "Device-code rehearsal started; Cloud IdP is not configured.",
                        {"pending_id": record["id"]})
        verify = DEMO_API + VERIFY_PATH
        return {
            "device_code": device_code,
            "user_code": user_code,
            "verification_uri": verify,
            "verification_uri_complete": verify + "?user_code=" + user_code,
            "expires_in": int(DEVICE_TTL.total_seconds()),
            "interval": POLL_INTERVAL_SECONDS,
            "cloud_idp": CLOUD_IDP,
            "mints_session": False,
            "live_validated": False,
            "production_writes": False,
            "auth_kind": "DEVICE_CODE",
            "grant_type": DEVICE_GRANT,
        }

    def poll_device(self, device_code: str, grant_type: str | None = None) -> dict:
        self._require_demo()
        if grant_type not in (None, DEVICE_GRANT):
            raise ValueError("unsupported_grant_type")
        if not device_code or len(device_code) < 16:
            raise ValueError("invalid_grant")
        now = utcnow()
        record = self._by_device_code(device_code)
        if record is None:
            raise ValueError("invalid_grant")
        if record["expires_at"] <= now.isoformat() or record["status"] == "EXPIRED":
            if record["status"] != "EXPIRED":
                record["status"] = "EXPIRED"
                self.store.put(self.tenant, DEVICE_KIND, record["id"], record)
            raise ValueError("expired_token")
        if record["status"] != "PENDING":
            raise ValueError("invalid_grant")
        raise ValueError("authorization_pending")

    def exchange_token(self, grant_type: str, device_code: str | None = None,
                       code: str | None = None) -> dict:
        self._require_demo()
        if grant_type == DEVICE_GRANT:
            return self.poll_device(device_code or "", grant_type)
        if grant_type in {"authorization_code", "refresh_token"}:
            raise ValueError("cloud_idp_not_configured")
        raise ValueError("unsupported_grant_type")

    def refuse_authorize(self) -> None:
        self._require_demo()
        raise ValueError("cloud_idp_not_configured")

    def refuse_revoke_cloud_token(self) -> None:
        self._require_demo()
        raise ValueError("cloud_idp_not_configured")

    def verify_page(self) -> dict:
        self._require_demo()
        return {
            "cloud_idp": CLOUD_IDP,
            "mints_session": False,
            "live_validated": False,
            "production_writes": False,
            "placeholder_session_required": True,
            "message": (
                "FreightDesk Cloud identity is not configured. Use Demo sign-in "
                "(POST /v1/portable/session) on this demo API. Completing a user_code "
                "will not issue a device session."
            ),
        }

    def _pending(self):
        return self.store.all(self.tenant, DEVICE_KIND)

    def _by_device_code(self, device_code: str) -> dict | None:
        digest = token_digest(device_code)
        for item in self._pending():
            if hmac.compare_digest(item["device_code_digest"], digest):
                return item
        return None

    def _user_code(self) -> str:
        raw = "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(8))
        return raw[:4] + "-" + raw[4:]

    def _require_demo(self):
        if Settings.from_env().mode != "demo":
            raise PermissionError("demo_mode_required")

    def _audit(self, event: str, explanation: str, facts: dict):
        self.store.audit(AuditEvent(
            tenant_id=self.tenant,
            actor_id="portable-bridge",
            source="cloud_lease_oauth",
            event=event,
            explanation=explanation,
            facts=facts,
            verified=False,
        ))
