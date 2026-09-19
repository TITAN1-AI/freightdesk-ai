"""Demo-gated agent API sessions. Not cloud OAuth and not LIVE_VALIDATED."""

from __future__ import annotations

import hmac
import os
import secrets
from datetime import timedelta
from pathlib import Path

from app.core.config import Settings
from app.models.domain import AuditEvent, utcnow
from app.services.auth_tokens import token_digest

AGENT_KIND = "portable_agent"
AGENT_AUTH_KIND = "DEMO_AGENT"
AGENT_TTL = timedelta(days=30)
MAX_AGENT_SESSIONS = 8
MIN_AGENT_TOKEN_LEN = 32
AGENT_BOOTSTRAP_RELATIVE = "Tokens/demo-agent-token.txt"
AGENT_TOKEN_ENV = "FREIGHTDESK_AGENT_TOKEN"


class AgentSessionService:
    def __init__(self, store, tenant: str, bootstrap_path: Path | None = None):
        self.store = store
        self.tenant = tenant
        self.bootstrap_path = bootstrap_path

    def create_or_get(self) -> dict:
        self._require_demo()
        env_token = os.getenv(AGENT_TOKEN_ENV, "").strip()
        if env_token:
            if len(env_token) < MIN_AGENT_TOKEN_LEN:
                raise ValueError("agent_token_too_short")
            record = self._ensure_record(env_token, source="environment")
            return self._issued_view(env_token, record, source="environment")
        file_token = self._read_bootstrap()
        if file_token:
            record = self._ensure_record(file_token, source="bootstrap_file")
            return self._issued_view(file_token, record, source="bootstrap_file")
        token = secrets.token_urlsafe(32)
        record = self._ensure_record(token, source="issued")
        self._write_bootstrap(token)
        return self._issued_view(token, record, source="issued")

    def require(self, token: str) -> dict:
        record = self._from_token(token)
        now = utcnow().isoformat()
        if record is None or record["status"] != "ACTIVE" or record["expires_at"] <= now:
            raise PermissionError("agent_session_required")
        return record

    def has_session(self, token: str | None) -> bool:
        if not token:
            return False
        try:
            self.require(token)
            return True
        except PermissionError:
            return False

    def public_status(self, token: str | None) -> dict:
        base = {
            "mode": "demo",
            "product": "agent-ascend-api",
            "auth_kind": AGENT_AUTH_KIND,
            "live_validated": False,
            "production_writes": False,
            "not_oauth": True,
            "bootstrap_path": AGENT_BOOTSTRAP_RELATIVE,
            "signed_in": False,
        }
        if not self.has_session(token):
            return base
        record = self.require(token)
        return {
            **base,
            "signed_in": True,
            "agent_id": record["id"],
            "expires_at": record["expires_at"],
            "source": record.get("source"),
        }

    def _ensure_record(self, token: str, source: str) -> dict:
        now = utcnow()
        digest = token_digest(token)
        with self.store.transaction():
            existing = self._from_digest(digest)
            if existing is not None and existing["status"] == "ACTIVE" and existing["expires_at"] > now.isoformat():
                return existing
            active = [item for item in self._all()
                      if item["status"] == "ACTIVE" and item["expires_at"] > now.isoformat()]
            if existing is None and len(active) >= MAX_AGENT_SESSIONS:
                raise ValueError("agent_session_bound")
            record = existing or {
                "id": digest[:32],
                "token_digest": digest,
                "created_at": now.isoformat(),
                "auth_kind": AGENT_AUTH_KIND,
            }
            record["status"] = "ACTIVE"
            record["expires_at"] = (now + AGENT_TTL).isoformat()
            record["source"] = source
            self.store.put(self.tenant, AGENT_KIND, record["id"], record)
            if existing is None:
                self._audit("AGENT_SESSION_ISSUED", "Demo agent API session issued.",
                            {"agent_id": record["id"]})
            return record

    def _issued_view(self, token: str, record: dict, source: str) -> dict:
        return {
            "agent_id": record["id"],
            "agent_token": token,
            "expires_at": record["expires_at"],
            "auth_kind": AGENT_AUTH_KIND,
            "mode": "demo",
            "source": source,
            "bootstrap_path": AGENT_BOOTSTRAP_RELATIVE,
            "live_validated": False,
            "production_writes": False,
            "not_oauth": True,
        }

    def _read_bootstrap(self) -> str | None:
        path = self.bootstrap_path
        if path is None or not path.exists():
            return None
        token = path.read_text(encoding="utf-8").strip()
        if len(token) < MIN_AGENT_TOKEN_LEN:
            return None
        return token

    def _write_bootstrap(self, token: str) -> None:
        path = self.bootstrap_path
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def _all(self):
        return self.store.all(self.tenant, AGENT_KIND)

    def _from_token(self, token: str) -> dict | None:
        return self._from_digest(token_digest(token))

    def _from_digest(self, digest: str) -> dict | None:
        for item in self._all():
            if hmac.compare_digest(item["token_digest"], digest):
                return item
        return None

    def _require_demo(self):
        if Settings.from_env().mode != "demo":
            raise PermissionError("demo_mode_required")

    def _audit(self, event: str, explanation: str, facts: dict):
        self.store.audit(AuditEvent(
            tenant_id=self.tenant,
            actor_id="demo-agent",
            source="agent_session",
            event=event,
            explanation=explanation,
            facts=facts,
            verified=False,
        ))
