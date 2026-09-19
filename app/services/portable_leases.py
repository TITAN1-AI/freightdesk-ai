"""Demo-only portable browser-bridge leases. Not cloud auth and not LIVE_VALIDATED."""

from __future__ import annotations

import hmac
import secrets
from datetime import timedelta
from pathlib import Path

from pydantic import ValidationError

from app.core.config import Settings
from app.models.domain import AuditEvent, Model, utcnow
from app.services.agent_sessions import AgentSessionService
from app.services.auth_tokens import token_digest

ALLOWED_ORIGIN = "https://ascendtms.com"
HARVEST_SCOPE = "VISIBLE_BOARD_ONLY"
EVIDENCE_CLASS = "CANDIDATE"
MAX_DEVICE_SESSIONS = 8
MAX_ACTIVE_LEASES = 8
MAX_HARVEST_ROWS = 100
DEFAULT_LEASE_TTL_SECONDS = 900
MAX_LEASE_TTL_SECONDS = 28800
MIN_LEASE_TTL_SECONDS = 60
DEVICE_TTL = timedelta(hours=8)
LOAD_STATUSES = frozenset({
    "Active", "Available", "Assigned", "Booked", "Dispatched",
    "In Transit", "Delivered", "Completed", "UNKNOWN",
})


class HarvestRow(Model):
    load_id: str
    pick_date: str | None = None
    drop_date: str | None = None
    load_status: str = "UNKNOWN"


class HarvestSnapshot(Model):
    lease_id: str
    origin: str
    view: str
    view_confidence: str
    coverage: str
    evidence_class: str
    live_validated: bool
    values_included: bool
    production_writes: bool
    revision: str
    captured_at: str
    row_count: int
    rows: list[HarvestRow]


def validate_harvest_snapshot(payload: object) -> HarvestSnapshot:
    if not isinstance(payload, dict):
        raise ValueError("harvest_payload_invalid")
    try:
        snapshot = HarvestSnapshot.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("harvest_payload_invalid") from exc
    if snapshot.origin != ALLOWED_ORIGIN:
        raise ValueError("origin_not_allowlisted")
    if snapshot.view != "ACTIVE_LOADS":
        raise ValueError("view_not_active_loads")
    if snapshot.view_confidence != "VERIFIED":
        raise ValueError("view_unverified")
    if snapshot.coverage != HARVEST_SCOPE:
        raise ValueError("coverage_unsupported")
    if snapshot.evidence_class != EVIDENCE_CLASS:
        raise ValueError("evidence_class_unsupported")
    if snapshot.live_validated:
        raise ValueError("live_validated_forbidden")
    if snapshot.values_included:
        raise ValueError("values_included_forbidden")
    if snapshot.production_writes:
        raise ValueError("production_writes_forbidden")
    if snapshot.row_count != len(snapshot.rows):
        raise ValueError("row_count_mismatch")
    if snapshot.row_count > MAX_HARVEST_ROWS:
        raise ValueError("row_count_bound")
    if len(snapshot.revision) != 64 or any(ch not in "0123456789abcdef" for ch in snapshot.revision):
        raise ValueError("revision_invalid")
    ids: list[str] = []
    for row in snapshot.rows:
        if not row.load_id.isdigit() or not (1 <= len(row.load_id) <= 20):
            raise ValueError("row_identity_invalid")
        for value in (row.pick_date, row.drop_date):
            if value is not None and _invalid_board_date(value):
                raise ValueError("row_date_invalid")
        if row.load_status not in LOAD_STATUSES:
            raise ValueError("row_status_invalid")
        ids.append(row.load_id)
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate_load_id")
    if not snapshot.captured_at or len(snapshot.captured_at) > 64:
        raise ValueError("captured_at_invalid")
    return snapshot


def _invalid_board_date(value: str) -> bool:
    if len(value) != 10 or value[2] != "/" or value[5] != "/":
        return True
    month, day, year = value.split("/")
    return not (month.isdigit() and day.isdigit() and year.isdigit() and len(year) == 4)


class PortableLeaseService:
    def __init__(self, store, tenant: str, agents: AgentSessionService | None = None,
                 agent_bootstrap_path: Path | None = None):
        self.store = store
        self.tenant = tenant
        self.agents = agents or AgentSessionService(store, tenant, bootstrap_path=agent_bootstrap_path)

    def create_device_session(self) -> dict:
        self._require_demo()
        token = secrets.token_urlsafe(32)
        now = utcnow()
        expires = now + DEVICE_TTL
        with self.store.transaction():
            sessions = self._devices()
            active = [item for item in sessions if item["status"] == "ACTIVE" and item["expires_at"] > now.isoformat()]
            if len(active) >= MAX_DEVICE_SESSIONS:
                raise ValueError("device_session_bound")
            record = {
                "id": token_digest(token)[:32],
                "token_digest": token_digest(token),
                "status": "ACTIVE",
                "created_at": now.isoformat(),
                "expires_at": expires.isoformat(),
                "auth_kind": "PLACEHOLDER",
            }
            self.store.put(self.tenant, "portable_device", record["id"], record)
            self._audit("PORTABLE_DEVICE_SESSION", "Demo portable device session issued.", {"device_id": record["id"]})
        return {
            "device_id": record["id"],
            "device_token": token,
            "expires_at": record["expires_at"],
            "auth_kind": "PLACEHOLDER",
            "mode": "demo",
            "live_validated": False,
            "production_writes": False,
        }

    def create_lease(self, device_token: str, origin: str, scope: str, ttl_seconds: int) -> dict:
        self._require_demo()
        principal = self._require_principal(device_token)
        if origin != ALLOWED_ORIGIN:
            raise ValueError("origin_not_allowlisted")
        if scope != HARVEST_SCOPE:
            raise ValueError("scope_unsupported")
        if not isinstance(ttl_seconds, int) or ttl_seconds < MIN_LEASE_TTL_SECONDS or ttl_seconds > MAX_LEASE_TTL_SECONDS:
            raise ValueError("ttl_unsupported")
        token = secrets.token_urlsafe(32)
        now = utcnow()
        expires = now + timedelta(seconds=ttl_seconds)
        with self.store.transaction():
            active = [item for item in self._leases() if item["status"] == "ACTIVE" and item["expires_at"] > now.isoformat()]
            if len(active) >= MAX_ACTIVE_LEASES:
                raise ValueError("lease_bound")
            record = {
                "id": secrets.token_hex(16),
                "token_digest": token_digest(token),
                "device_id": principal["id"],
                "owner_kind": principal["kind"],
                "origin": origin,
                "scope": scope,
                "status": "ACTIVE",
                "created_at": now.isoformat(),
                "expires_at": expires.isoformat(),
                "harvest_count": 0,
                "last_harvest_at": None,
                "last_revision": None,
            }
            self.store.put(self.tenant, "portable_lease", record["id"], record)
            self._audit("PORTABLE_LEASE_CREATED",
                        "Demo portable VISIBLE_BOARD_ONLY lease issued.",
                        {"lease_id": record["id"], "origin": origin, "scope": scope})
        return self._lease_view(record, lease_token=token)

    def revoke_lease(self, device_token: str, lease_id: str) -> dict:
        principal = self._require_principal(device_token)
        with self.store.transaction():
            record = self._lease_record(lease_id)
            if record["device_id"] != principal["id"]:
                raise PermissionError("lease_not_owned")
            record["status"] = "REVOKED"
            record["revoked_at"] = utcnow().isoformat()
            self.store.put(self.tenant, "portable_lease", record["id"], record)
            self._audit("PORTABLE_LEASE_REVOKED", "Portable harvest lease revoked.", {"lease_id": record["id"]})
        return self._lease_view(record)

    def accept_harvest(self, lease_token: str, payload: object) -> dict:
        self._require_demo()
        snapshot = validate_harvest_snapshot(payload)
        now = utcnow()
        with self.store.transaction():
            record = self._lease_by_token(lease_token)
            self._require_active_lease(record, now)
            if snapshot.lease_id != record["id"]:
                raise PermissionError("lease_mismatch")
            if snapshot.origin != record["origin"] or snapshot.coverage != record["scope"]:
                raise PermissionError("lease_scope_mismatch")
            stored = {
                "lease_id": record["id"],
                "accepted_at": now.isoformat(),
                "captured_at": snapshot.captured_at,
                "origin": snapshot.origin,
                "view": snapshot.view,
                "revision": snapshot.revision,
                "row_count": snapshot.row_count,
                "coverage": snapshot.coverage,
                "evidence_class": snapshot.evidence_class,
                "live_validated": False,
                "production_writes": False,
                "rows": [row.model_dump() for row in snapshot.rows],
            }
            record["harvest_count"] = int(record["harvest_count"]) + 1
            record["last_harvest_at"] = now.isoformat()
            record["last_revision"] = snapshot.revision
            self.store.put(self.tenant, "portable_lease", record["id"], record)
            self.store.put(self.tenant, "portable_harvest", record["id"], stored)
            self._audit("PORTABLE_HARVEST_ACCEPTED",
                        "CANDIDATE VISIBLE_BOARD_ONLY board snapshot stored.",
                        {"lease_id": record["id"], "row_count": snapshot.row_count, "revision": snapshot.revision})
        return {
            "accepted": True,
            "lease_id": record["id"],
            "revision": snapshot.revision,
            "row_count": snapshot.row_count,
            "evidence_class": EVIDENCE_CLASS,
            "coverage": HARVEST_SCOPE,
            "live_validated": False,
            "production_writes": False,
        }

    def status(self, device_token: str | None) -> dict:
        base = {
            "mode": "demo",
            "product": "portable-bridge",
            "track": "B",
            "live_validated": False,
            "production_writes": False,
            "allowed_origins": [ALLOWED_ORIGIN],
            "scope": HARVEST_SCOPE,
            "evidence_class": EVIDENCE_CLASS,
            "signed_in": False,
            "auth_kind": None,
            "lease": None,
            "harvest": None,
        }
        if not device_token:
            return base
        principal = self._require_principal(device_token)
        now = utcnow().isoformat()
        leases = [item for item in self._leases() if item["device_id"] == principal["id"]]
        current = next((item for item in leases if item["status"] == "ACTIVE" and item["expires_at"] > now), None)
        harvest = None
        if current:
            try:
                stored = self.store.get(self.tenant, "portable_harvest", current["id"])
                harvest = {
                    "lease_id": stored["lease_id"],
                    "accepted_at": stored["accepted_at"],
                    "revision": stored["revision"],
                    "row_count": stored["row_count"],
                    "evidence_class": stored["evidence_class"],
                    "live_validated": False,
                }
            except KeyError:
                harvest = None
        extra = {"device_id": principal["id"], "device_expires_at": principal["expires_at"]}
        if principal["kind"] == "agent":
            extra = {"agent_id": principal["id"], "agent_expires_at": principal["expires_at"]}
        return {
            **base,
            "signed_in": True,
            "auth_kind": principal["auth_kind"],
            **extra,
            "lease": None if current is None else self._lease_view(current),
            "harvest": harvest,
        }

    def has_device_session(self, token: str | None) -> bool:
        if not token:
            return False
        try:
            self._require_device(token)
            return True
        except PermissionError:
            return False

    def has_agent_session(self, token: str | None) -> bool:
        return self.agents.has_session(token)

    def has_api_caller(self, token: str | None) -> bool:
        return self.has_device_session(token) or self.has_agent_session(token)

    def facade_status(self) -> dict:
        self._require_demo()
        lease, harvest = self._facade_lease_and_harvest()
        row_count = 0 if harvest is None else int(harvest["row_count"])
        last_at = None if harvest is None else harvest.get("accepted_at")
        return {
            "facade": "ascend",
            "source": "portable_harvest",
            "actuator": "portable-bridge",
            "mode": "demo",
            "live_validated": False,
            "production_writes": False,
            "evidence_class": EVIDENCE_CLASS,
            "coverage": HARVEST_SCOPE,
            "not_a_retail_api": True,
            "lease_active": bool(lease and lease["status"] == "ACTIVE"
                                 and lease["expires_at"] > utcnow().isoformat()),
            "lease_status": "NONE" if lease is None else lease["status"],
            "lease_id": None if lease is None else lease["id"],
            "lease_expires_at": None if lease is None else lease["expires_at"],
            "harvest_available": harvest is not None,
            "harvest_count": 0 if lease is None else int(lease.get("harvest_count") or 0),
            "last_harvest_at": last_at,
            "extension_last_seen": last_at,
            "row_count": row_count,
            "revision": None if harvest is None else harvest.get("revision"),
        }

    def facade_loads(self) -> dict:
        self._require_demo()
        lease, harvest = self._facade_lease_and_harvest()
        loads = [] if harvest is None else [self._facade_load(row) for row in harvest.get("rows") or []]
        return {
            "facade": "ascend",
            "source": "portable_harvest",
            "not_a_retail_api": True,
            "view": "ACTIVE_LOADS",
            "coverage": HARVEST_SCOPE,
            "evidence_class": EVIDENCE_CLASS,
            "live_validated": False,
            "production_writes": False,
            "lease_id": None if harvest is None else harvest.get("lease_id"),
            "lease_status": "NONE" if lease is None else lease["status"],
            "harvested_at": None if harvest is None else harvest.get("accepted_at"),
            "revision": None if harvest is None else harvest.get("revision"),
            "load_count": len(loads),
            "loads": loads,
        }

    def _facade_lease_and_harvest(self) -> tuple[dict | None, dict | None]:
        now = utcnow().isoformat()
        harvests = sorted(self.store.all(self.tenant, "portable_harvest"),
                          key=lambda item: item.get("accepted_at") or "", reverse=True)
        harvest = harvests[0] if harvests else None
        leases = self._leases()
        active = next((item for item in leases
                       if item["status"] == "ACTIVE" and item["expires_at"] > now), None)
        owning = None
        if harvest is not None:
            owning = next((item for item in leases if item["id"] == harvest["lease_id"]), None)
        return active or owning, harvest

    def _facade_load(self, row: dict) -> dict:
        fields = {}
        status = row.get("load_status")
        if status is not None:
            fields["load_status"] = {"value": status, "evidence_class": EVIDENCE_CLASS}
        return {
            "load_id": row["load_id"],
            "pick_date": row.get("pick_date"),
            "drop_date": row.get("drop_date"),
            "evidence_class": EVIDENCE_CLASS,
            "fields": fields,
        }

    def _require_demo(self):
        if Settings.from_env().mode != "demo":
            raise PermissionError("demo_mode_required")

    def _devices(self):
        return self.store.all(self.tenant, "portable_device")

    def _leases(self):
        return self.store.all(self.tenant, "portable_lease")

    def _device_from_token(self, token: str) -> dict | None:
        digest = token_digest(token)
        for item in self._devices():
            if hmac.compare_digest(item["token_digest"], digest):
                return item
        return None

    def _require_device(self, token: str) -> dict:
        device = self._device_from_token(token)
        now = utcnow().isoformat()
        if device is None or device["status"] != "ACTIVE" or device["expires_at"] <= now:
            raise PermissionError("device_session_required")
        return device

    def _require_principal(self, token: str) -> dict:
        """Extension device placeholder or demo agent Bearer. Both may own leases."""
        try:
            device = self._require_device(token)
            return {
                "id": device["id"],
                "kind": "device",
                "auth_kind": device.get("auth_kind", "PLACEHOLDER"),
                "expires_at": device["expires_at"],
            }
        except PermissionError:
            pass
        try:
            agent = self.agents.require(token)
            return {
                "id": agent["id"],
                "kind": "agent",
                "auth_kind": agent["auth_kind"],
                "expires_at": agent["expires_at"],
            }
        except PermissionError:
            raise PermissionError("device_session_required") from None

    def _lease_record(self, lease_id: str) -> dict:
        return self.store.get(self.tenant, "portable_lease", lease_id)

    def _lease_by_token(self, token: str) -> dict:
        digest = token_digest(token)
        for item in self._leases():
            if hmac.compare_digest(item["token_digest"], digest):
                return item
        raise PermissionError("lease_required")

    def _require_active_lease(self, record: dict, now):
        if record["status"] == "REVOKED":
            raise PermissionError("lease_revoked")
        if record["expires_at"] <= now.isoformat():
            record["status"] = "EXPIRED"
            self.store.put(self.tenant, "portable_lease", record["id"], record)
            raise PermissionError("lease_expired")
        if record["status"] != "ACTIVE":
            raise PermissionError("lease_inactive")

    def _lease_view(self, record: dict, lease_token: str | None = None) -> dict:
        view = {
            "id": record["id"],
            "origin": record["origin"],
            "scope": record["scope"],
            "status": record["status"],
            "created_at": record["created_at"],
            "expires_at": record["expires_at"],
            "harvest_count": record["harvest_count"],
            "last_harvest_at": record["last_harvest_at"],
            "last_revision": record["last_revision"],
            "live_validated": False,
            "production_writes": False,
            "evidence_class": EVIDENCE_CLASS,
        }
        if lease_token is not None:
            view["lease_token"] = lease_token
        return view

    def _audit(self, event: str, explanation: str, facts: dict):
        self.store.audit(AuditEvent(
            tenant_id=self.tenant,
            actor_id="portable-bridge",
            source="portable_lease",
            event=event,
            explanation=explanation,
            facts=facts,
            verified=False,
        ))
