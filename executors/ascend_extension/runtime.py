"""Owner-enabled, host-scheduled Ascend reads. Runtime proposals never mutate canonical state.

This database is separate from all historical bootstrap/read-grant ledgers. It contains
append-only authorization, request, audit and provider-proposal history plus a recoverable
scheduler checkpoint. Construction/status alone neither enroll nor enable anything.
"""

import hashlib
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import get_args

from pydantic import ValidationError

from executors.ascend_extension.controller import (
    FindEvidence,
    IdentityEvidence,
    SessionEvidence,
    policy_gate,
    safe_code,
)
from executors.ascend_extension.board_schema import Predicate
from executors.ascend_extension.bridge_build import BUILD
from executors.ascend_extension.detail_contract import DetailDiscoveryEvidence
from executors.ascend_extension.detail_diagnostics import BOUND_CODES, DetailContainerDiagnostic
from executors.ascend_extension.native import canonical
from executors.ascend_extension.workspace_contracts import MAP_OPERATION, AUTO_OPERATION, MAPPING_ERRORS, MappingCommand, MappingSessionApproval, AutoMapNavigationCommand
from executors.ascend_extension.mapping_store import persist_map, require_mapping_validation
from executors.ascend_extension.auto_map import plan_auto_map, accept_transition
from executors.ascend_extension.pairing import ACTOR, TENANT
from executors.ascend_extension.runtime_contracts import (
    RUNTIME_OPERATIONS,
    RuntimeBoardEvidence,
    RuntimeCommand,
    RuntimeResult, RuntimeMappingProgress, RuntimeCaptureAck,
    RuntimeViewEvidence,
    RuntimeWake,
    UnknownDetailEvidence,
)

from executors.ascend_extension.mapping_diagnostics import STAGES, MappingSectionDiagnostic, record_diagnostic

DEFAULT_HOURS = 8
DEFAULT_INTERVAL_SECONDS = 300
ERRORS = frozenset(
    {
        "CAUSAL_TRACE_BOUND", "CAUSAL_TRACE_INVALID",
        "DETAIL_CONTRACT_INVALID", "DETAIL_CONTRACT_UNAVAILABLE", "DETAIL_CONTAINER_UNVERIFIED", "DETAIL_BOUND_CONTAINERS", "DETAIL_BOUND_ATTRIBUTES", "DETAIL_BOUND_CONTROLS", "DETAIL_BOUND_HEADINGS", "DETAIL_BOUND_CANDIDATES", "DETAIL_BOUND_DEPTH", "DETAIL_ATTEMPT_CONSUMED", "DETAIL_DISCOVERY_COMPLETE",
        'CONTENT_SCRIPT_MISSING', 'CONTENT_SCRIPT_OLD_VERSION', 'CONTENT_SCRIPT_PORT_STALE', 'DOCUMENT_CHANGED', 'PROTOCOL_VERSION_MISMATCH', 'CONTENT_SCRIPT_INJECTION_BLOCKED', 'CONTENT_SCRIPT_RECOVERY_FAILED',
        "READ_ACCESS_DISABLED", "CONTENT_SCRIPT_STALE", "REFRESH_ASCEND_TAB", "TAB_DISCOVERY_FAILED", "SCHEDULER_NOT_RUNNING", "NAVIGATION_UNVERIFIED",
        "READ_LEASE_EXPIRED",
        "READ_LEASE_REVOKED",
        "OWNER_REQUIRED",
        "RUNTIME_PAUSED",
        "SECURITY_MISMATCH",
        "RUNTIME_SCOPE_INVALID",
        "RUNTIME_SEQUENCE_INVALID",
        "DUPLICATE_REQUEST",
        "READ_TIMEOUT",
        "SESSION_UNVERIFIED",
        "ASCEND_REAUTH_REQUIRED",
        "NAVIGATION_STARTED",
        "TAB_STATE_CHANGED",
        "READ_POLICY_BLOCKED",
        "RUNTIME_PROBE_BOUND",
        "RUNTIME_PERSIST_FAILED",
        "RECEIPT_INVALID",
        "BOARD_SCHEMA_INVALID",
        "BOARD_CHANGED",
        "ACTIVE_VIEW_CHANGED",
        "ACTIVE_VIEW_UNVERIFIED",
        "ACTIVE_VIEW_NOT_ACTIVE_LOADS",
        "EXACT_LOAD_MISSING",
        "DETAIL_IDENTITY_CONFLICT",
        "DETAIL_IDENTITY_MISSING",
        "DETAIL_IDENTITY_AMBIGUOUS",
        "FIELD_CONTRACT_UNKNOWN",
        "READ_EXECUTION_FAILED",
        "NO_ELIGIBLE_TAB",
        "TAB_SELECTION_REQUIRED",
        "OPENER_AMBIGUOUS",
        "UNSAFE_OPENER",
    }
) | BOUND_CODES | MAPPING_ERRORS


def runtime_code(error):
    raw = error if isinstance(error, str) else error.args[0] if len(error.args) == 1 else ""
    return raw if isinstance(raw, str) and raw in ERRORS else safe_code(error)


def enrollment_guard(repo):
    from executors.ascend_extension.enrollment import EnrollmentRepository

    return EnrollmentRepository(repo).load()


def _initial():
    return {
        "state": "READ_ACCESS_DISABLED",
        "session": "UNKNOWN",
        "view": "UNKNOWN",
        "bound_tab": "UNBOUND",
        "route": None,
        "pending": None,
        "step": 0,
        "next_due_at": 0,
        "last_board_sync": None,
        "board_hash": None,
        "load_count": 0,
        "last_heartbeat": None, "last_wake_at": None, "execution_stage": None, "eligible_tab_count": None,
        "last_session_at": None,
        "paused": False,
        "control_revision": 0,
        "revoked_generation": None,
        "error_code": None,
        "detail_attempt": None,
        "detail_load": None,
        "detail_step": 0,
        "identity_verified": False,
        "probe_window": 0,
        "probe_count": 0,
        "mapping_capture_requested": False, "mapping_capture_count": 0, "mapping_proof_route": None,
        "owner_present": False, "owner_presence_verified_at": None,
    }


class RuntimeAccess:
    """Only local authenticated owner surfaces call enable/disable/pause/rebind/queue_detail."""

    def __init__(self, repo, *, enrollment_guard=None, gate=policy_gate, clock=time.time):
        self.repo, self.gate, self.clock = repo, gate, clock
        self.enrollment_guard = enrollment_guard or (lambda: globals()["enrollment_guard"](repo))

    @property
    def path(self):
        return self.repo.path("runtime.sqlite3")

    @contextmanager
    def database(self, *, readonly=False):
        if readonly:
            db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=3)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path, timeout=3)
        try:
            with db:
                if not readonly:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_leases(id TEXT PRIMARY KEY,body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_events(seq INTEGER PRIMARY KEY,body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_requests(id TEXT PRIMARY KEY)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_proposals(id TEXT PRIMARY KEY,body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_receipts(id TEXT PRIMARY KEY,body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_detail_attempts(id TEXT PRIMARY KEY,body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_detail_contracts(id INTEGER PRIMARY KEY,body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_capture_events(id INTEGER PRIMARY KEY,body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_mapping_wakes(id INTEGER PRIMARY KEY,created_at REAL NOT NULL)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_mapping_diagnostics(id INTEGER PRIMARY KEY,body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_mapping_sessions(id TEXT PRIMARY KEY,body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_provider_maps(id INTEGER PRIMARY KEY,body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_mapping_validations(id TEXT PRIMARY KEY,body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_navigation_contracts(id INTEGER PRIMARY KEY,body TEXT)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_auto_map_cycles(id INTEGER PRIMARY KEY,body TEXT)")
                    from executors.ascend_extension.mapping_store import ensure_map_indexes
                    ensure_map_indexes(db)
                    for table in ('runtime_auto_map_cycles', 'runtime_mapping_diagnostics', 'runtime_capture_events'):
                        db.execute(f"CREATE INDEX IF NOT EXISTS {table}_session ON {table}(json_extract(body,'$.session_id'),id)")
                    db.execute("CREATE TABLE IF NOT EXISTS runtime_state(id INTEGER PRIMARY KEY,body TEXT)")
                    for table in (
                        "runtime_detail_attempts",
                        "runtime_detail_contracts",
                        "runtime_mapping_wakes", "runtime_capture_events", "runtime_mapping_diagnostics", "runtime_mapping_sessions", "runtime_provider_maps", "runtime_mapping_validations", "runtime_navigation_contracts", "runtime_auto_map_cycles",
                        "runtime_leases",
                        "runtime_events",
                        "runtime_requests",
                        "runtime_proposals",
                        "runtime_receipts",
                    ):
                        for operation in ("UPDATE", "DELETE"):
                            db.execute(
                                f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation} BEFORE {operation} ON {table} "
                                "BEGIN SELECT RAISE(ABORT, 'append_only_runtime_history'); END"
                            )
                yield db
        finally:
            db.close()

    @staticmethod
    def _load(db):
        item = db.execute("SELECT body FROM runtime_state WHERE id=1").fetchone()
        lease = db.execute("SELECT body FROM runtime_leases ORDER BY rowid DESC LIMIT 1").fetchone()
        return json.loads(item[0]) if item else _initial(), json.loads(lease[0]) if lease else None

    @staticmethod
    def _save(db, state):
        db.execute("INSERT OR REPLACE INTO runtime_state VALUES (1,?)", (json.dumps(state),))

    def _audit(self, db, kind, code, *, operation=None, count=None, schema_predicate=None, detail_diagnostic=None):
        # Fixed vocabulary only; provider values, exception text and bindings cannot enter audits.
        if kind not in {"LEASE", "CONTROL", "DISPATCH", "RECEIPT", "PROPOSAL", "SECURITY"}:
            raise ValueError("RUNTIME_SCOPE_INVALID")
        safe = {
            "timestamp": datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(),
            "tenant_id": TENANT,
            "actor": ACTOR,
            "kind": kind,
            "result_code": code
            if code
            in ERRORS
            | {
                "ENABLED",
                "DISABLED",
                "PAUSED",
                "RESUMED",
                "REBIND",
                "QUEUED",
                "DISPATCHED",
                "VERIFIED",
                "BOARD_UNCHANGED",
                "BOARD_REFRESHED",
                "UNKNOWN",
            }
            else "READ_EXECUTION_FAILED",
            "operation": operation if operation in (*RUNTIME_OPERATIONS, MAP_OPERATION, AUTO_OPERATION) else None,
            "record_count": count if type(count) is int and 0 <= count <= 100 else None,
            "production_writes": False,
        }
        if schema_predicate in get_args(Predicate):
            safe["schema_predicate"] = schema_predicate
        if detail_diagnostic is not None:
            detail = DetailContainerDiagnostic.model_validate(detail_diagnostic)
            safe["detail_container_diagnostic"] = detail.model_dump()
        db.execute("INSERT INTO runtime_events(body) VALUES (?)", (json.dumps(safe),))

    @staticmethod
    def _owner(owner_authorized):
        if owner_authorized is not True:
            raise PermissionError("OWNER_REQUIRED")

    def notify_mapping_job(self):
        """Durable local wake hint; neither grants authority nor dispatches a provider action."""
        with self.database() as db:
            db.execute("INSERT INTO runtime_mapping_wakes(created_at) VALUES (?)", (self.clock(),))
            state, lease = self._load(db)
            self._causal(db, state, lease, "WAKE_WRITTEN")

    def _causal(self, db, state, lease, event, reason=None, metadata=None):
        from executors.ascend_extension.causal_trace import emit
        return emit(db, state, lease, event, reason=reason, metadata=metadata, now=self.clock())

    def causal_event(self, event, reason=None, metadata=None):
        if not self.path.exists():
            return False
        with self.database() as db:
            state, lease = self._load(db)
            return self._causal(db, state, lease, event, reason, metadata)

    def mapping_wake_sequence(self):
        if not self.path.exists():
            return 0
        with self.database(readonly=True) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='runtime_mapping_wakes'").fetchone():
                return 0
            return db.execute("SELECT COALESCE(MAX(id),0) FROM runtime_mapping_wakes").fetchone()[0]

    _UNSPECIFIED_GENERATION = object()

    def enable(
        self, *, owner_authorized=False, hours=DEFAULT_HOURS, interval_seconds=DEFAULT_INTERVAL_SECONDS,
        mapping: MappingSessionApproval | None = None,
        expected_previous_generation=_UNSPECIFIED_GENERATION,
    ):
        self._owner(owner_authorized)
        if mapping is not None:
            mapping = MappingSessionApproval.model_validate(mapping)
            hours, interval_seconds = mapping.minutes / 60, 60
            if mapping.mode == "NORMAL_OWNER_PRESENT" and mapping.operation_mode == "AUTO_MAP":
                if not self.path.exists():
                    raise PermissionError("MAPPING_VALIDATION_REQUIRED")
                with self.database(readonly=True) as db:
                    require_mapping_validation(db)
        if (
            type(hours) not in (int, float)
            or not 1 / 60 <= hours <= 24
            or type(interval_seconds) is not int
            or not 60 <= interval_seconds <= 3600
        ):
            raise ValueError("RUNTIME_SCOPE_INVALID")
        self.gate(self.repo)
        enrollment = self.enrollment_guard()
        config = self.repo.config()
        if enrollment["installation_id"] != config["installation_id"]:
            raise PermissionError("SECURITY_MISMATCH")
        grant = {
            "generation": secrets.token_hex(16),
            "enrollment_generation": enrollment["generation"],
            "installation_id": config["installation_id"],
            "tenant_id": TENANT,
            "actor": ACTOR,
            "issued_at": int(self.clock()),
            "expires_at": int(self.clock() + hours * 3600),
            "interval_seconds": interval_seconds,
            "allowed_operations": [RUNTIME_OPERATIONS[0], MAP_OPERATION] if mapping else list(RUNTIME_OPERATIONS),
            "writes": "FORBIDDEN",
        }
        if mapping and mapping.authority_expires_at is not None:
            if mapping.authority_expires_at <= self.clock():
                raise PermissionError("READ_LEASE_EXPIRED")
            grant["expires_at"] = min(grant["expires_at"], mapping.authority_expires_at)
        if mapping:
            grant["mapping"] = mapping.model_dump()
            if mapping.operation_mode == "AUTO_MAP":
                grant["allowed_operations"].append(AUTO_OPERATION)
        if mapping and mapping.session_only:
            grant["allowed_operations"] = [RUNTIME_OPERATIONS[0]]
        with self.database() as db:
            old, previous = self._load(db)
            if (expected_previous_generation is not self._UNSPECIFIED_GENERATION
                and (previous["generation"] if previous else None) != expected_previous_generation):
                raise PermissionError("READ_JOB_ACTIVE")
            if previous and previous.get("mapping", {}).get("orchestrated"):
                self._causal(db, old, previous, "SESSION_PROOF_INVALIDATED", "LEASE_GENERATION_CHANGED")
            if mapping:
                if mapping.mode == "NORMAL_OWNER_PRESENT" and mapping.operation_mode == "AUTO_MAP":
                    require_mapping_validation(db)
                if db.execute("SELECT 1 FROM runtime_mapping_sessions WHERE id=?", (mapping.session_id,)).fetchone():
                    raise PermissionError("MAPPING_SESSION_CONSUMED")
                db.execute("INSERT INTO runtime_mapping_sessions VALUES (?,?)", (mapping.session_id, json.dumps(mapping.model_dump())))
            state = _initial()
            state.update(
                control_revision=old["control_revision"] + 1,
                state="PAUSED" if old["paused"] else "DISCOVERING_ASCEND",
                paused=old["paused"],
                last_heartbeat=old["last_heartbeat"],
                board_hash=old["board_hash"],
                last_board_sync=old["last_board_sync"],
                load_count=old["load_count"],
            )
            # Readiness may survive an immediate scope transition; session and route proof do not.
            # Every dispatch still requires a new signed, document-bound foreground check.
            if mapping and old.get("owner_present") and old.get("owner_presence_verified_at") is not None and 0 <= self.clock()-old["owner_presence_verified_at"] <= 3:
                state.update(owner_present=True, owner_presence_verified_at=old["owner_presence_verified_at"])
            db.execute("INSERT INTO runtime_leases VALUES (?,?)", (grant["generation"], json.dumps(grant)))
            self._save(db, state)
            self._audit(db, "LEASE", "ENABLED")
        return self.status()

    def request_mapping_capture(self, *, owner_authorized=False, expected_mapping_session_id=None):
        self._owner(owner_authorized)
        lease = self.check()
        if not lease.get("mapping") or lease["mapping"].get("session_only"):
            raise PermissionError("MAPPING_NOT_ENABLED")
        with self.database() as db:
            state, current = self._load(db)
            if expected_mapping_session_id is not None and (current or {}).get("mapping", {}).get("session_id") != expected_mapping_session_id:
                raise PermissionError("READ_LEASE_REVOKED")
            if current["generation"] != lease["generation"] or state["revoked_generation"] == lease["generation"] or state["paused"]:
                raise PermissionError("READ_LEASE_REVOKED")
            if self.clock() >= lease["expires_at"]:
                raise PermissionError("READ_LEASE_EXPIRED")
            if state["state"] == "STOPPED":
                raise PermissionError(state["error_code"] or "MAPPING_NOT_ENABLED")
            if state.get("mapping_capture_requested") or state["pending"]:
                raise PermissionError("MAPPING_CAPTURE_PENDING")
            if state.get("mapping_capture_count", 0) >= lease["mapping"]["max_captures"]:
                raise PermissionError("MAPPING_CAPTURE_BOUND")
            state.update(mapping_capture_requested=True, mapping_proof_route=None, next_due_at=0)
            self._save(db, state)
            self._audit(db, "CONTROL", "QUEUED", operation=MAP_OPERATION)
        return self.status()

    def disable(self, *, owner_authorized=False, expected_mapping_session_ids=None):
        self._owner(owner_authorized)
        self.invalidate("READ_LEASE_REVOKED", expected_mapping_session_ids=expected_mapping_session_ids)
        return self.status()

    def invalidate(self, code="SECURITY_MISMATCH", *, expected_mapping_session_ids=None):
        if not self.path.exists():
            return
        with self.database() as db:
            state, lease = self._load(db)
            if expected_mapping_session_ids is not None and (lease or {}).get("mapping", {}).get("session_id") not in expected_mapping_session_ids:
                return  # A coordinator may revoke only its own exact mapping authority.
            try:
                self._causal(db, state, lease, "SESSION_PROOF_INVALIDATED", "LEASE_REVOKED")
            except PermissionError as error:
                if error.args != ("CAUSAL_TRACE_BOUND",):
                    raise
                # A full diagnostic budget must never prevent authority revocation.
                state["causal_trace_bound"] = True
            state.update(
                revoked_generation=lease["generation"] if lease else None,
                mapping_capture_requested=False, mapping_proof_route=None,
                pending=None,
                route=None,
                bound_tab="UNBOUND",
                session="UNKNOWN",
                view="UNKNOWN",
                state="STOPPED",
                error_code=runtime_code(code),
                control_revision=state["control_revision"] + 1,
            )
            if code == "SECURITY_MISMATCH":
                state["last_heartbeat"] = None
            self._save(db, state)
            self._audit(db, "SECURITY", runtime_code(code))

    def set_paused(self, paused, *, owner_authorized=False):
        self._owner(owner_authorized)
        if type(paused) is not bool:
            raise ValueError("RUNTIME_SCOPE_INVALID")
        with self.database() as db:
            state, _ = self._load(db)
            state.update(
                paused=paused,
                mapping_capture_requested=False, mapping_proof_route=None,
                pending=None,
                step=0,
                detail_load=None,
                identity_verified=False,
                next_due_at=0,
                state="PAUSED" if paused else "DISCOVERING_ASCEND",
                error_code=None,
                control_revision=state["control_revision"] + 1,
            )
            self._save(db, state)
            self._audit(db, "CONTROL", "PAUSED" if paused else "RESUMED")
        return self.status()

    def request_rebind(self, *, owner_authorized=False):
        self._owner(owner_authorized)
        with self.database() as db:
            state, _ = self._load(db)
            state.update(
                route=None,
                pending=None,
                bound_tab="UNBOUND",
                session="UNKNOWN",
                view="UNKNOWN",
                step=0,
                next_due_at=0,
                detail_load=None,
                identity_verified=False,
                state="DISCOVERING_ASCEND",
                error_code=None,
                control_revision=state["control_revision"] + 1,
            )
            self._save(db, state)
            self._audit(db, "CONTROL", "REBIND")
        return self.status()

    def status(self):
        # Deliberately no DPAPI access or database creation for dashboard polling.
        state, lease = _initial(), None
        if self.path.exists():
            with self.database(readonly=True) as db:
                state, lease = self._load(db)
        return self._project(state, lease)

    def _project(self, state, lease):
        access = (
            "DISABLED"
            if not lease
            else "REVOKED"
            if state["revoked_generation"] == lease["generation"]
            else "EXPIRED"
            if self.clock() >= lease["expires_at"]
            else "ENABLED"
        )
        fresh = state["last_heartbeat"] is not None and 0 <= self.clock() - state["last_heartbeat"] <= 120
        # Dashboard freshness is a last-observation label, never an execution gate. The host
        # still requests a new session proof at the start of every scheduled board cycle.
        session_horizon = lease["interval_seconds"] + 60 if lease else 120
        session_fresh = (
            fresh
            and state.get("last_session_at") is not None
            and 0 <= self.clock() - state["last_session_at"] <= session_horizon
        )
        result_state = (
            state["state"]
            if access == "ENABLED"
            else {
                "DISABLED": "PAIRED" if fresh else "READ_ACCESS_DISABLED",
                "EXPIRED": "READ_LEASE_EXPIRED",
                "REVOKED": "STOPPED",
            }[access]
        )
        if state["paused"] and access == "ENABLED":
            result_state = "PAUSED"
        scheduler_stale = access == "ENABLED" and not state["paused"] and self.clock() - (state.get("last_wake_at") or lease["issued_at"]) > 150
        if scheduler_stale and result_state not in {"STOPPED", "CONTENT_SCRIPT_STALE", "TAB_DISCOVERY_FAILED"}:
            result_state = "SCHEDULER_NOT_RUNNING"
        if result_state == "STOPPED" and state.get("execution_stage") == "ASCEND_NAVIGATE_ACTIVE_LOADS":
            result_state = "VIEW_UNVERIFIED"
        action = (
            "Sign into Ascend."
            if state["session"] == "ASCEND_REAUTH_REQUIRED"
            else "Select an Ascend tab."
            if result_state == "TAB_SELECTION_REQUIRED"
            else "Open Ascend."
            if result_state == "WAITING_FOR_ASCEND"
            else "Enable read-only access."
            if access != "ENABLED"
            else "Review the safe error code."
            if result_state == "STOPPED"
            else None
        )
        if result_state == "SCHEDULER_NOT_RUNNING":
            action = "Open Edge with X1 enabled."
        elif result_state == "CONTENT_SCRIPT_STALE":
            action = "REFRESH_ASCEND_TAB"
        elif result_state == "TAB_DISCOVERY_FAILED":
            action = "Check X1 site access and the safe discovery result."
        elif result_state == "VIEW_UNVERIFIED":
            action = "Review the recorded Active Loads navigation error."
        current_board = (access == "ENABLED" and not state["paused"] and session_fresh
                         and state["session"] == "AUTHENTICATED" and state["view"] == "ACTIVE_LOADS"
                         and state["bound_tab"] == "ACTIVE" and state["state"] == "READ_ONLY_READY"
                         and state["last_board_sync"] is not None
                         and self.clock() - state["last_board_sync"] <= session_horizon)
        if state["error_code"] in {"CONTENT_SCRIPT_INJECTION_BLOCKED", "CONTENT_SCRIPT_RECOVERY_FAILED", "PROTOCOL_VERSION_MISMATCH"}:
            result_state = state["error_code"] if access == "ENABLED" else result_state
            action = "Check the installed X1 build and Edge extension policy; do not refresh or re-pair."
        return {
            "build": BUILD,
            "owner_present": bool(access == "ENABLED" and state.get("owner_present") and state.get("owner_presence_verified_at") is not None and 0 <= self.clock()-state["owner_presence_verified_at"] <= 3),
            "owner_presence_verified_at": state.get("owner_presence_verified_at"),
            "mapping_mode": bool(lease and lease.get("mapping")),
            "mapping_orchestrated": bool(lease and lease.get("mapping", {}).get("orchestrated")),
            "mapping_operation_mode": lease["mapping"]["operation_mode"] if lease and lease.get("mapping") else None,
            "auto_map_active": bool(state.get("auto_plan")),
            "auto_last_cycle": state.get("auto_last_cycle"),
            "mapping_scope": lease["mapping"]["mode"] if lease and lease.get("mapping") else None,
            "mapping_session_id": lease["mapping"]["session_id"] if lease and lease.get("mapping") else None,
            "mapping_capture_requested": state.get("mapping_capture_requested", False),
            "mapping_capture_count": state.get("mapping_capture_count", 0),
            "mapping_capture_limit": lease["mapping"]["max_captures"] if lease and lease.get("mapping") else None,
            "mapping_last_summary": state.get("mapping_last_summary"),
            "mapping_diagnostic": state.get("mapping_diagnostic"),
            "mapping_workspace_count": state.get("mapping_workspace_count", 0),
            "mapping_section_count": state.get("mapping_section_count", 0),
            "mapping_contract_count": state.get("mapping_contract_count", 0),
            "mapping_noop": state.get("mapping_noop", False),
            "mapping_wait_reason": state.get("mapping_wait_reason"),
            "mapping_owner_change_at": state.get("mapping_owner_change_at"),
            "mapping_limits": {k: lease["mapping"][k] for k in ("minutes", "max_captures", "max_workspace_captures", "max_section_observations", "max_contract_observations")} if lease and lease.get("mapping") else None,
            "schema_predicate": state.get("schema_predicate"),
            "board_schema_diagnostic": state.get("board_schema_diagnostic"),
            "detail_container_diagnostic": state.get("detail_container_diagnostic"),
            "document_handshake": state.get("document_handshake"),
            "board_evidence_status": "CURRENT_VERIFIED_BOARD" if current_board else "LAST_KNOWN_BOARD_EVIDENCE" if state["last_board_sync"] else "NO_BOARD_EVIDENCE",
            "execution_stage": state.get("execution_stage"),
            "eligible_tab_count": state.get("eligible_tab_count"),
            "scheduler": "NOT_RUNNING" if scheduler_stale else "RUNNING" if state.get("last_wake_at") and self.clock()-state["last_wake_at"] <= 150 else "UNKNOWN",
            "last_scheduler_wake": state.get("last_wake_at"),
            "state": result_state,
            "read_access": access,
            "session": state["session"] if session_fresh else "UNKNOWN",
            "view": state["view"] if session_fresh else "UNKNOWN",
            "pairing": "VALID" if fresh else "UNKNOWN",
            "extension": "CONNECTED" if fresh else "DISCONNECTED",
            "native_host": "CONNECTED" if fresh else "DISCONNECTED",
            "bound_tab": state["bound_tab"] if session_fresh else "UNBOUND",
            "lease_expires_at": lease["expires_at"] if lease else None,
            "next_due_at": state["next_due_at"],
            "last_board_sync": state["last_board_sync"],
            "board_hash": state["board_hash"],
            "load_count": state["load_count"] if state["last_board_sync"] is not None else None,
            "paused": state["paused"],
            "error_code": state["error_code"],
            "action": action,
            "control_revision": state["control_revision"],
            "production_writes": False,
        }

    def check(self):
        self.gate(self.repo)
        status = self.status()
        if status["read_access"] != "ENABLED":
            raise PermissionError(
                {
                    "DISABLED": "READ_ACCESS_DISABLED",
                    "EXPIRED": "READ_LEASE_EXPIRED",
                    "REVOKED": "READ_LEASE_REVOKED",
                }[status["read_access"]]
            )
        if status["paused"]:
            raise PermissionError("RUNTIME_PAUSED")
        try:
            enrollment = self.enrollment_guard()
            with self.database(readonly=True) as db:
                _, lease = self._load(db)
            expected_operations = list(RUNTIME_OPERATIONS)
            if lease.get("mapping"):
                MappingSessionApproval.model_validate(lease["mapping"])
                if lease["mapping"]["mode"] == "NORMAL_OWNER_PRESENT" and lease["mapping"]["operation_mode"] == "AUTO_MAP":
                    with self.database(readonly=True) as db:
                        require_mapping_validation(db)
                expected_operations = [RUNTIME_OPERATIONS[0], MAP_OPERATION]
                if lease["mapping"]["operation_mode"] == "AUTO_MAP":
                    expected_operations.append(AUTO_OPERATION)
            if lease.get("mapping", {}).get("session_only"):
                expected_operations = [RUNTIME_OPERATIONS[0]]
            if (
                lease["enrollment_generation"] != enrollment["generation"]
                or lease["installation_id"] != enrollment["installation_id"]
                or lease["installation_id"] != self.repo.config()["installation_id"]
                or lease["allowed_operations"] != expected_operations
                or lease["writes"] != "FORBIDDEN"
                or lease["tenant_id"] != TENANT
                or lease["actor"] != ACTOR
            ):
                raise PermissionError("SECURITY_MISMATCH")
        except Exception:
            self.invalidate("SECURITY_MISMATCH")
            raise PermissionError("SECURITY_MISMATCH") from None
        return lease

    def queue_detail(self, load_id, *, owner_authorized=False):
        self._owner(owner_authorized)
        return self.request_detail_for_workflow(load_id)

    def queue_discovery(self, load_id, attempt_id, *, owner_authorized=False):
        self._owner(owner_authorized)
        if not isinstance(attempt_id, str) or not re.fullmatch(r"owner-x1-detail-[a-z0-9-]{1,64}", attempt_id):
            raise ValueError("RUNTIME_SCOPE_INVALID")
        return self.request_detail_for_workflow(load_id, attempt_id=attempt_id)

    def request_detail_for_workflow(self, load_id, *, attempt_id=None):
        """Trusted FreightDesk workflow entry; intentionally absent from browser/native messages.

        Existing owner lease authorizes this bounded request. It cannot accept selectors,
        arbitrary fields, operations, tenant overrides or an ID outside the fresh board.
        """
        checked_lease = self.check()
        if checked_lease.get("mapping"):
            raise PermissionError("RUNTIME_SCOPE_INVALID")
        if not isinstance(load_id, str) or not re.fullmatch(r"[0-9]{1,20}", load_id):
            raise ValueError("RUNTIME_SCOPE_INVALID")
        with self.database() as db:
            state, lease = self._load(db)
            if (lease["generation"] != checked_lease["generation"] or state["state"] == "STOPPED"
                or state["paused"] or state["revoked_generation"] == lease["generation"]
                or self.clock() >= lease["expires_at"]):
                raise PermissionError("READ_POLICY_BLOCKED")
            if (
                state["pending"]
                or state["detail_load"]
                or not state["board_hash"]
                or not state["last_board_sync"]
                or self.clock() - state["last_board_sync"] > lease["interval_seconds"]
            ):
                raise PermissionError("BOARD_CHANGED")
            body = db.execute("SELECT body FROM runtime_proposals ORDER BY rowid DESC LIMIT 1").fetchone()
            proposal = json.loads(body[0]) if body else {}
            if proposal.get("derived", {}).get("semantic_board_hash") != state[
                "board_hash"
            ] or load_id not in {r["load_id"] for r in proposal.get("provider_facts", [])}:
                raise PermissionError("EXACT_LOAD_MISSING")
            if attempt_id is not None:
                if (state["state"] != "READ_ONLY_READY" or state["session"] != "AUTHENTICATED"
                    or state["bound_tab"] != "ACTIVE" or state["last_board_sync"] < lease["issued_at"]):
                    raise PermissionError("BOARD_CHANGED")
                if db.execute("SELECT 1 FROM runtime_detail_attempts WHERE id=?", (attempt_id,)).fetchone():
                    raise PermissionError("DETAIL_ATTEMPT_CONSUMED")
                try:
                    db.execute("INSERT INTO runtime_detail_attempts VALUES (?,?)", (attempt_id, json.dumps({
                        "attempt_id": attempt_id, "lease_generation": lease["generation"], "load_id": load_id,
                        "board_hash": state["board_hash"], "queued_at": self.clock(), "status": "CONSUMED",
                        "production_writes": False})))
                except sqlite3.IntegrityError:
                    raise PermissionError("DETAIL_ATTEMPT_CONSUMED") from None
            state.update(detail_attempt=attempt_id, detail_load=load_id, detail_step=0, identity_verified=False, step=0, next_due_at=0,
                         detail_container_diagnostic=None)
            self._save(db, state)
            self._audit(db, "CONTROL", "QUEUED")
        return self.status()


class RuntimeController:
    def __init__(self, repo, *, enrollment_guard=None, gate=policy_gate, clock=time.time):
        self.access = RuntimeAccess(repo, enrollment_guard=enrollment_guard, gate=gate, clock=clock)
        self.repo, self.clock = repo, clock

    def invalidate(self, code="SECURITY_MISMATCH"):
        self.access.invalidate(code)

    def bridge_failure(self, code):
        if code not in {"PROTOCOL_VERSION_MISMATCH", "DOCUMENT_CHANGED"}:
            raise ValueError("RUNTIME_SCOPE_INVALID")
        with self.access.database() as db:
            state, _ = self.access._load(db)
            state.update(state=code, error_code=code, pending=None, route=None, bound_tab="UNBOUND",
                         session="UNKNOWN", view="UNKNOWN", step=0, next_due_at=0)
            self.access._audit(db, "CONTROL", code)
            self.access._save(db, state)

    def _status(self):
        status = self.access.status()
        hint = None
        if status["read_access"] == "ENABLED" and not status["paused"] and self.access.path.exists():
            with self.access.database(readonly=True) as db:
                state, _ = self.access._load(db)
            if state["route"] and state["bound_tab"] == "ACTIVE":
                hint = {k: state["route"][k] for k in ("tab_id", "document_id")}
        return {"kind": "RUNTIME_STATUS", "status": status, "binding_hint": hint}

    def status(self):
        self._heartbeat()
        return self._status()

    def _heartbeat(self):
        """A verified local channel may advertise connectivity with all read access disabled."""
        try:
            enrollment = self.access.enrollment_guard()
            if enrollment["installation_id"] != self.repo.config()["installation_id"]:
                raise PermissionError("SECURITY_MISMATCH")
        except Exception:
            self.invalidate("SECURITY_MISMATCH")
            raise PermissionError("SECURITY_MISMATCH") from None
        mismatch = False
        with self.access.database() as db:
            state, lease = self.access._load(db)
            if (
                lease
                and state["revoked_generation"] != lease["generation"]
                and lease["enrollment_generation"] != enrollment["generation"]
            ):
                mismatch = True
                state.update(
                    revoked_generation=lease["generation"],
                    pending=None,
                    route=None,
                    bound_tab="UNBOUND",
                    state="STOPPED",
                    error_code="SECURITY_MISMATCH",
                    session="UNKNOWN",
                    view="UNKNOWN",
                    control_revision=state["control_revision"] + 1,
                )
                self.access._audit(db, "SECURITY", "SECURITY_MISMATCH")
            state["last_heartbeat"] = self.clock()
            if mismatch:
                state["last_heartbeat"] = None
            self.access._save(db, state)
        if mismatch:
            raise PermissionError("SECURITY_MISMATCH")

    @staticmethod
    def _consume(db, request_id):
        try:
            db.execute("INSERT INTO runtime_requests VALUES (?)", (request_id,))
        except sqlite3.IntegrityError:
            raise PermissionError("DUPLICATE_REQUEST") from None

    def wake(self, raw):
        try:
            request = RuntimeWake.model_validate(raw)
        except ValidationError:
            raise PermissionError("PROTOCOL_VERSION_MISMATCH") from None
        self._heartbeat()
        with self.access.database() as db:
            wake_state, _ = self.access._load(db)
            wake_state["last_wake_at"] = self.clock()
            self.access._save(db, wake_state)
        try:
            lease = self.access.check()
        except PermissionError as error:
            result = self._status()
            result["status"]["error_code"] = runtime_code(error)
            return result
        with self.access.database() as db:
            self._consume(db, request.request_id)
            state, current = self.access._load(db)
            if (
                current["generation"] != lease["generation"]
                or state["revoked_generation"] == lease["generation"]
                or state["paused"]
            ):
                raise PermissionError("READ_LEASE_REVOKED")
            if self.clock() >= lease["expires_at"]:
                raise PermissionError("READ_LEASE_EXPIRED")
            state["last_heartbeat"] = self.clock()
            if request.handshake is not None:
                state["document_handshake"] = request.handshake.model_dump()
            if request.routing_state is not None:
                self.access._causal(db, state, lease, "SESSION_PROOF_INVALIDATED",
                    request.routing_error or "ROUTING_PROOF_INVALIDATED")
                state.update(owner_present=False, owner_presence_verified_at=None, mapping_proof_route=None)
                if state.get("detail_attempt"):
                    state.update(state="STOPPED", error_code="TAB_STATE_CHANGED", pending=None,
                                 detail_load=None, identity_verified=False, bound_tab="UNBOUND")
                    self.access._audit(db, "CONTROL", "TAB_STATE_CHANGED")
                    self.access._save(db, state)
                    return self._status_from(state, current)
                state.update(
                    state=request.routing_state,
                    eligible_tab_count=request.eligible_tab_count,
                    execution_stage="TAB_DISCOVERY",
                    route=None,
                    pending=None,
                    bound_tab="UNBOUND",
                    session="ASCEND_REAUTH_REQUIRED"
                    if request.routing_state == "ASCEND_REAUTH_REQUIRED"
                    else "UNKNOWN",
                    view="UNKNOWN",
                    step=0,
                    next_due_at=0,
                    detail_load=None,
                    identity_verified=False,
                    error_code="TAB_SELECTION_REQUIRED"
                    if request.routing_state == "TAB_SELECTION_REQUIRED"
                    else "REFRESH_ASCEND_TAB" if request.routing_state == "CONTENT_SCRIPT_STALE"
                    else "TAB_DISCOVERY_FAILED" if request.routing_state == "TAB_DISCOVERY_FAILED" else None,
                )
                if request.routing_error is not None:
                    state["error_code"] = request.routing_error
                self.access._audit(db, "CONTROL", state["error_code"] or "VERIFIED", count=request.eligible_tab_count)
                self.access._save(db, state)
                return self._status_from(state, current)
            if state["pending"]:
                if self.clock() >= state["pending"]["deadline"]:
                    if state["pending"]["command"]["operation"] == MAP_OPERATION:
                        record_diagnostic(db, state, lease, state["pending"], self.clock(), "READ_TIMEOUT")
                    state.update(
                        pending=None,
                        step=0,
                        session="UNKNOWN",
                        view="UNKNOWN",
                        state="STOPPED",
                        error_code="READ_TIMEOUT",
                        next_due_at=self.clock() + lease["interval_seconds"],
                    )
                    self.access._audit(db, "RECEIPT", "READ_TIMEOUT", operation=state.get("execution_stage"))
                self.access._save(db, state)
                return self._status_from(state, current)
            if state["state"] == "STOPPED":
                self.access._save(db, state)
                return self._status_from(state, current)
            if request.route is None:
                self.access._save(db, state)
                return self._status_from(state, current)
            route = request.route.model_dump()
            if lease.get("mapping"):
                state.update(route=route, bound_tab="ACTIVE")
                if lease["mapping"].get("orchestrated"):
                    # Presence is an independent fresh private-content receipt, never inferred from
                    # an active-tab query, a previous load, or a retained session proof.
                    state.update(owner_present=request.owner_present is True,
                                 owner_presence_verified_at=self.clock() if request.owner_present is True else None)
                    self.access._causal(db, state, lease,
                        "OWNER_READINESS_PROVED" if request.owner_present is True else "SESSION_PROOF_INVALIDATED",
                        None if request.owner_present is True else "OWNER_NOT_PRESENT")
                    if request.owner_present is not True:
                        state.update(state="WAITING_FOR_OWNER_WORKSPACE", error_code=None,
                                     mapping_proof_route=None, next_due_at=0)
                        self.access._save(db, state)
                        return self._status_from(state, current)
                if request.mapping_hint:
                    state["mapping_owner_change_at"] = self.clock()
                if (request.mapping_hint and lease["mapping"]["mode"] == "NORMAL_OWNER_PRESENT"
                    and self.clock() - state.get("mapping_last_dispatch", 0) >= 2):
                    state["next_due_at"] = 0
                if request.probe_only or state.get("mapping_proof_route") != route or self.clock() - (state.get("last_session_at") or 0) > 60:
                    if state.get("last_session_at") and self.clock() - state["last_session_at"] > 60:
                        self.access._causal(db, state, lease, "SESSION_PROOF_INVALIDATED", "SESSION_RECEIPT_EXPIRED")
                    if self.clock() - state["probe_window"] >= 60:
                        state.update(probe_window=self.clock(), probe_count=0)
                    if state["probe_count"] >= 10:
                        raise PermissionError("RUNTIME_PROBE_BOUND")
                    state["probe_count"] += 1
                    operation = RUNTIME_OPERATIONS[0]
                elif state.get("auto_plan") or state.get("mapping_capture_requested") or lease["mapping"]["mode"] == "NORMAL_OWNER_PRESENT" and not lease["mapping"].get("orchestrated") and self.clock() >= state["next_due_at"]:
                    self.access._causal(db, state, lease, "CAPTURE_DISPATCH_ATTEMPTED")
                    if state.get("mapping_capture_count", 0) >= lease["mapping"]["max_captures"]:
                        state.update(state="STOPPED", error_code="MAPPING_CAPTURE_BOUND", auto_plan=None)
                        self.access._save(db, state)
                        return self._status_from(state, current)
                    if state.get("auto_plan") and state.get("mapping_section_count", 0) >= lease["mapping"]["max_section_observations"]:
                        state.update(state="STOPPED", error_code="MAPPING_SECTION_BOUND", auto_plan=None)
                        self.access._save(db, state)
                        return self._status_from(state, current)
                    state["mapping_capture_count"] = state.get("mapping_capture_count", 0) + 1
                    state["mapping_capture_requested"] = False
                    state["mapping_last_dispatch"] = self.clock()
                    operation = AUTO_OPERATION if state.get("auto_plan") else MAP_OPERATION
                else:
                    state.update(state="MAPPING_READY", next_due_at=self.clock() + 60, error_code=None)
                    self.access._save(db, state)
                    return self._status_from(state, current)
            elif request.probe_only:
                if self.clock() - state["probe_window"] >= 60:
                    state.update(probe_window=self.clock(), probe_count=0)
                if state["probe_count"] >= 10:
                    raise PermissionError("RUNTIME_PROBE_BOUND")
                state["probe_count"] += 1
                operation = RUNTIME_OPERATIONS[0]
            else:
                if state["route"] != route:
                    if state.get("detail_attempt"):
                        state.update(state="STOPPED", error_code="TAB_STATE_CHANGED", detail_load=None, identity_verified=False)
                        self.access._save(db, state)
                        return self._status_from(state, current)
                    state.update(
                        route=route,
                        step=0,
                        session="UNKNOWN",
                        view="UNKNOWN",
                        bound_tab="UNBOUND",
                        next_due_at=0,
                        detail_load=None,
                        identity_verified=False,
                    )
                if state["step"] == 0 and self.clock() < state["next_due_at"]:
                    self.access._save(db, state)
                    return self._status_from(state, current)
                operation = (
                    RUNTIME_OPERATIONS[state["step"]]
                    if state["step"] < 3
                    else RUNTIME_OPERATIONS[3 + state["detail_step"]]
                )
                if state["step"] >= 3 and state.get("detail_attempt") and state["detail_step"] == 2:
                    operation = "ASCEND_DISCOVER_DETAIL_CONTRACT"
                if state["step"] >= 3 and not state["detail_load"]:
                    raise PermissionError("RUNTIME_SEQUENCE_INVALID")
                if operation in RUNTIME_OPERATIONS[5:] and not state["identity_verified"]:
                    raise PermissionError("DETAIL_IDENTITY_MISSING")
            command = AutoMapNavigationCommand(request_id=secrets.token_hex(16), approved_load_ids=lease["mapping"]["approved_load_ids"],
                owner_present=True, lease_expires_at=lease["expires_at"], load_id=state["auto_plan"]["load_id"],
                navigation=state["auto_plan"]["contracts"][0], expected_from_section=state["auto_plan"]["current_section"],
                return_to_start=len(state["auto_plan"]["contracts"]) == 1) if operation == AUTO_OPERATION else MappingCommand(request_id=secrets.token_hex(16), capture_load_id=lease["mapping"].get("capture_load_id"), capture_section=lease["mapping"].get("capture_section"), approved_load_ids=lease["mapping"]["approved_load_ids"],
                owner_present=lease["mapping"]["mode"] == "NORMAL_OWNER_PRESENT" or lease["mapping"].get("orchestrated", False), lease_expires_at=lease["expires_at"]) if operation == MAP_OPERATION else RuntimeCommand(
                request_id=secrets.token_hex(16),
                operation=operation,
                load_id=state["detail_load"] if operation in RUNTIME_OPERATIONS[3:] else None,
                expected_revision=state["board_hash"] if operation in RUNTIME_OPERATIONS[3:] else None,
            )
            pending = {
                "command": command.model_dump(),
                "route": route,
                "deadline": min(self.clock() + 12, lease["expires_at"]),
                "lease_generation": lease["generation"],
                "probe_only": request.probe_only,
                "document_handshake": state.get("document_handshake"),
            }
            state["execution_stage"] = operation
            state["eligible_tab_count"] = route["eligible_tab_count"]
            if operation == MAP_OPERATION:
                self.access._causal(db, state, lease, "CAPTURE_DISPATCHED")
                self._capture_event(db, lease, pending, "DISPATCHED")
                state["mapping_diagnostic"] = dict(stage="TAB_VERIFIED", candidate_workspace_count=0, identity_signal_count=0, section_control_count=0, elapsed_ms=0)
                record_diagnostic(db, state, lease, pending, self.clock())
            state["pending"] = pending
            self.access._save(db, state)
            self.access._audit(db, "DISPATCH", "DISPATCHED", operation=operation)
            if operation == RUNTIME_OPERATIONS[0]:
                self.access._causal(db, state, lease, "SESSION_PROOF_REQUESTED")
            return {
                "kind": "RUNTIME_DISPATCH",
                **{k: pending[k] for k in ("command", "route", "deadline", "lease_generation")},
            }

    def _status_from(self, state, lease):
        # Project the transaction's checkpoint without reading stale state on another connection.
        status = self.access._project(state, lease)
        hint = None
        if (
            status["read_access"] == "ENABLED"
            and not state["paused"]
            and state["route"]
            and state["bound_tab"] == "ACTIVE"
        ):
            hint = {k: state["route"][k] for k in ("tab_id", "document_id")}
        return {"kind": "RUNTIME_STATUS", "status": status, "binding_hint": hint}

    def _capture_event(self, db, lease, pending, stage):
        db.execute("INSERT INTO runtime_capture_events(body) VALUES (?)", (json.dumps({
            "session_id": lease["mapping"]["session_id"], "command_request_id": pending["command"]["request_id"],
            "state": stage, "at": self.clock(), "production_writes": False}),))

    def capture_ack(self, raw):
        ack = RuntimeCaptureAck.model_validate(raw)
        lease = self.access.check()
        with self.access.database() as db:
            self._consume(db, ack.request_id)
            state, current = self.access._load(db)
            pending = state["pending"]
            if (not pending or pending["command"]["operation"] != MAP_OPERATION
                or pending["command"]["request_id"] != ack.command_request_id
                or pending["route"] != ack.route.model_dump() or self.clock() >= pending["deadline"]
                or current["generation"] != lease["generation"] or pending["lease_generation"] != lease["generation"]
                or pending.get("capture_acknowledged")):
                raise PermissionError("RUNTIME_SEQUENCE_INVALID")
            pending["capture_acknowledged"] = True
            self._capture_event(db, lease, pending, "ACKNOWLEDGED")
            self.access._causal(db, state, lease, "CAPTURE_ACKNOWLEDGED")
            self.access._save(db, state)
        return {"kind": "RUNTIME_MAPPING_PROGRESS_ACK"}

    def mapping_progress(self, raw):
        request = RuntimeMappingProgress.model_validate(raw)
        lease = self.access.check()
        with self.access.database() as db:
            self._consume(db, request.request_id)
            state, current = self.access._load(db)
            pending = state["pending"]
            if (not pending or current["generation"] != lease["generation"]
                or pending["lease_generation"] != lease["generation"]
                or pending["command"]["operation"] != MAP_OPERATION
                or pending["command"]["request_id"] != request.command_request_id
                or pending["route"] != request.route.model_dump()
                or self.clock() >= pending["deadline"]):
                raise PermissionError("RUNTIME_SEQUENCE_INVALID")
            prior = state.get("mapping_diagnostic", {})
            if (request.diagnostic.stage == "MAP_PERSISTED"
                or STAGES.index(request.diagnostic.stage) != STAGES.index(prior["stage"]) + 1
                or request.diagnostic.elapsed_ms < prior["elapsed_ms"]):
                raise PermissionError("RUNTIME_SEQUENCE_INVALID")
            state["mapping_diagnostic"] = request.diagnostic.model_dump()
            record_diagnostic(db, state, lease, pending, self.clock())
            self.access._save(db, state)
        return {"kind": "RUNTIME_MAPPING_PROGRESS_ACK"}

    def finish(self, raw):
        result = RuntimeResult.model_validate(raw)
        lease = self.access.check()  # Expiry/revoke/policy/enrollment rechecked before receipt acceptance.
        failure = None
        with self.access.database() as db:
            self._consume(db, result.request_id)
            state, current = self.access._load(db)
            pending = state["pending"]
            if result.build is not None and not state.get("document_handshake"):
                raise PermissionError("PROTOCOL_VERSION_MISMATCH")
            if not pending or pending["command"]["request_id"] != result.command_request_id:
                raise PermissionError("RUNTIME_SEQUENCE_INVALID")
            if (
                current["generation"] != lease["generation"]
                or pending["lease_generation"] != lease["generation"]
                or state["revoked_generation"] == lease["generation"]
                or state["paused"]
            ):
                raise PermissionError("READ_LEASE_REVOKED")
            operation = pending["command"]["operation"]
            contract_savepoint = operation in {"ASCEND_DISCOVER_DETAIL_CONTRACT", MAP_OPERATION, AUTO_OPERATION}
            saved_state = json.loads(json.dumps(state)) if contract_savepoint else None
            if contract_savepoint:
                db.execute("SAVEPOINT detail_observation")
            try:
                if self.clock() >= pending["deadline"]:
                    raise PermissionError("READ_TIMEOUT")
                if result.route.model_dump() != pending["route"]:
                    raise PermissionError("TAB_STATE_CHANGED")
                if result.error_code is not None:
                    raise PermissionError(runtime_code(result.error_code))
                self._accept(db, state, lease, pending, result.evidence)
                receipt = {
                    "provider": "AscendTMS",
                    "source": "live extension DOM",
                    "observed_at": self.clock(),
                    "tenant_id": TENANT,
                    "actor": ACTOR,
                    "tenant_identity_source": "OWNER_ATTESTED",
                    "operation": operation,
                    "attempt_id": state.get("detail_attempt"),
                    "lease_generation": lease["generation"],
                    "evidence": result.evidence,
                    "route": {k: pending["route"][k] for k in ("origin", "path", "eligible_tab_count")},
                    "production_writes": False,
                    "document_handshake": pending.get("document_handshake"),
                }
                if operation == AUTO_OPERATION:
                    receipt["navigation_contract"] = pending["command"]["navigation"]
                    receipt["expected_load_id"] = pending["command"]["load_id"]
                    receipt["return_to_start"] = pending["command"]["return_to_start"]
                db.execute(
                    "INSERT INTO runtime_receipts VALUES (?,?)",
                    (pending["command"]["request_id"], json.dumps(receipt)),
                )
                self.access._audit(db, "RECEIPT", "VERIFIED", operation=operation)
                if operation == RUNTIME_OPERATIONS[0]:
                    self.access._causal(db, state, lease, "SESSION_PROOF_SUCCEEDED")
                if contract_savepoint:
                    db.execute("RELEASE detail_observation")
            except Exception as error:
                if contract_savepoint:
                    db.execute("ROLLBACK TO detail_observation")
                    db.execute("RELEASE detail_observation")
                    state = saved_state
                failure = runtime_code(error)
                if operation in {MAP_OPERATION, AUTO_OPERATION} and isinstance(result.evidence, dict):
                    # Retain only the typed structural diagnostic from a rejected capture.
                    # Neither raw failure payloads nor unvalidated provider values enter storage.
                    section_raw = result.evidence.get("section_diagnostic")
                    if section_raw is not None:
                        try:
                            section = MappingSectionDiagnostic.model_validate(section_raw)
                        except ValidationError:
                            section = None
                        if section is not None and state.get("mapping_diagnostic"):
                            state["mapping_diagnostic"]["section_diagnostic"] = section.model_dump()
                diagnostic = None
                if isinstance(result.evidence, dict) and set(result.evidence) <= {"view_contract", "schema_diagnostic", "detail_container_diagnostic"} and "view_contract" in result.evidence:
                    try:
                        diagnostic = RuntimeViewEvidence.model_validate(result.evidence)
                    except Exception:
                        diagnostic = None
                detail = diagnostic.detail_container_diagnostic if diagnostic is not None else None
                if detail is not None:
                    state["detail_container_diagnostic"] = detail.model_dump()
                if failure == "BOARD_SCHEMA_INVALID":
                    structural = diagnostic.schema_diagnostic if diagnostic is not None else None
                    predicate = structural.failed_predicate if structural else None
                    state["schema_predicate"] = predicate or state.get("pending_schema_predicate") or "STRUCTURAL_METADATA_UNAVAILABLE"
                    state["board_schema_diagnostic"] = structural.model_dump() if structural else None
                if diagnostic is not None:
                    safe_failure = {
                        "provider": "AscendTMS",
                        "source": "live extension DOM",
                        "observed_at": self.clock(),
                        "tenant_id": TENANT,
                        "actor": ACTOR,
                        "tenant_identity_source": "OWNER_ATTESTED",
                        "operation": operation,
                        "error_code": failure,
                        "attempt_id": state.get("detail_attempt"),
                        "schema_predicate": state.get("schema_predicate") if failure == "BOARD_SCHEMA_INVALID" else None,
                        "evidence": {k: v for k, v in diagnostic.model_dump().items() if v is not None},
                        "production_writes": False,
                    }
                    db.execute(
                        "INSERT INTO runtime_receipts VALUES (?,?)",
                        (pending["command"]["request_id"], json.dumps(safe_failure)),
                    )
                recover = failure in {
                    "NAVIGATION_STARTED", "DOCUMENT_CHANGED", "CONTENT_SCRIPT_PORT_STALE",
                    "ASCEND_REAUTH_REQUIRED",
                    "SESSION_UNVERIFIED",
                    "NO_ELIGIBLE_TAB",
                    "TAB_STATE_CHANGED",
                }
                if lease.get("mapping") or state.get("detail_attempt") or failure == "TAB_STATE_CHANGED" and operation in RUNTIME_OPERATIONS[3:]:
                    recover = False
                state.update(
                    state="ASCEND_REAUTH_REQUIRED"
                    if failure in {"ASCEND_REAUTH_REQUIRED", "SESSION_UNVERIFIED"}
                    else "NAVIGATING_ACTIVE_LOADS"
                    if recover
                    else "STOPPED",
                    error_code=failure,
                    step=0,
                    session="ASCEND_REAUTH_REQUIRED"
                    if failure in {"ASCEND_REAUTH_REQUIRED", "SESSION_UNVERIFIED"}
                    else "UNKNOWN",
                    view="UNKNOWN",
                    next_due_at=self.clock() + (5 if recover else lease["interval_seconds"]),
                    identity_verified=False,
                )
                if diagnostic is not None:
                    state["view"] = diagnostic.view_contract.view
                self.access._audit(db, "RECEIPT", failure, operation=operation,
                                   schema_predicate=state.get("schema_predicate") if failure == "BOARD_SCHEMA_INVALID" else None,
                                   detail_diagnostic=detail.model_dump() if detail else None)
            if operation == MAP_OPERATION:
                if failure is None:
                    self._capture_event(db, lease, pending, "COMPLETED")
                if failure is None and state.get("mapping_diagnostic"):
                    state["mapping_diagnostic"]["stage"] = "MAP_PERSISTED"
                record_diagnostic(db, state, lease, pending, self.clock(), failure)
            state.update(pending=None, last_heartbeat=self.clock())
            if (lease.get("mapping", {}).get("mode") == "NORMAL_OWNER_PRESENT" and not lease["mapping"].get("orchestrated") and operation == MAP_OPERATION
                and failure in {"WORKSPACE_IDENTITY_MISSING", "MAPPING_OWNER_NOT_PRESENT"}):
                # Owner left the load/browser; wait without inheriting the previous identity or opening anything.
                state.update(state="MAPPING_READY", error_code=None, mapping_proof_route=None,
                             mapping_capture_requested=False, mapping_last=None, mapping_wait_reason=failure)
            if operation == RUNTIME_OPERATIONS[0]:
                state["last_session_at"] = self.clock()
            self.access._save(db, state)
        return self._status()

    def _accept(self, db, state, lease, pending, raw):
        operation = pending["command"]["operation"]
        if operation not in lease["allowed_operations"]:
            raise PermissionError("RUNTIME_SCOPE_INVALID")
        if operation == RUNTIME_OPERATIONS[0]:
            evidence = SessionEvidence.model_validate(raw)
            markers = set(evidence.nav_markers)
            authenticated = (
                pending["route"]["path"] != "/login.html"
                and not evidence.login_form_present
                and {"Dashboard", "Loads"} <= markers
                and len(markers) >= 4
            )
            if evidence.authenticated_app != authenticated:
                raise PermissionError("RECEIPT_INVALID")
            if not authenticated:
                raise PermissionError("ASCEND_REAUTH_REQUIRED")
            state.update(
                session="AUTHENTICATED",
                last_session_at=self.clock(),
                error_code=None,
                state="BOUND",
            )
            if not pending["probe_only"]:
                state.update(step=1, bound_tab="ACTIVE")
            if lease.get("mapping"):
                state.update(mapping_proof_route=pending["route"], state="MAPPING_READY", bound_tab="ACTIVE")
            return
        if state["session"] != "AUTHENTICATED":
            raise PermissionError("SESSION_UNVERIFIED")
        if operation in {MAP_OPERATION, AUTO_OPERATION}:
            if not lease.get("mapping") or state.get("mapping_proof_route") != pending["route"]:
                raise PermissionError("MAPPING_NOT_ENABLED")
            adapter = getattr(self.access, "_offline_v2_adapter", None)
            record = (adapter.persist if adapter else persist_map)(db, state, lease, pending, raw, self.clock())
            state["mapping_noop"] = record is None
            if lease["mapping"]["operation_mode"] == "AUTO_MAP":
                if operation == MAP_OPERATION:
                    if record is not None or not state.get("auto_last_cycle"):
                        plan_auto_map(db, state, raw)
                else:
                    accept_transition(db, state, lease, pending, raw, self.clock())
            state.update(state="MAPPING_READY", next_due_at=self.clock() + 60, error_code=None, mapping_wait_reason=None)
            if state.get("auto_plan"):
                state["next_due_at"] = 0
            return
        if operation == RUNTIME_OPERATIONS[1]:
            evidence = RuntimeViewEvidence.model_validate(raw)
            evidence.view_contract.require_active()
            state.update(view="ACTIVE_LOADS", step=2, error_code=None)
            return
        if pending["route"]["path"] != "/loads" or state["view"] != "ACTIVE_LOADS":
            raise PermissionError("ACTIVE_VIEW_UNVERIFIED")
        if operation == RUNTIME_OPERATIONS[2]:
            evidence = RuntimeBoardEvidence.model_validate(raw)
            evidence.view_contract.require_active()
            rows = sorted((r.model_dump() for r in evidence.rows), key=lambda r: int(r["load_id"]))
            revision = hashlib.sha256(canonical(rows)).hexdigest()
            if len({r["load_id"] for r in rows}) != len(rows) or revision != evidence.board_hash:
                state["pending_schema_predicate"] = "HOST_DUPLICATE_LOAD_ID" if len({r["load_id"] for r in rows}) != len(rows) else "HOST_BOARD_HASH_MISMATCH"
                raise PermissionError("BOARD_SCHEMA_INVALID")
            state["pending_schema_predicate"] = None
            state["schema_predicate"] = None
            state["board_schema_diagnostic"] = evidence.schema_diagnostic.model_dump() if evidence.schema_diagnostic else None
            if state.get("detail_attempt"):
                queued = db.execute("SELECT body FROM runtime_detail_attempts WHERE id=?", (state["detail_attempt"],)).fetchone()
                if not queued or json.loads(queued[0])["board_hash"] != revision:
                    raise PermissionError("BOARD_CHANGED")
            changed = state["board_hash"] != revision
            if changed:
                proposal = {
                    "provider": "AscendTMS",
                    "source": "live extension DOM",
                    "observed_at": self.clock(),
                    "tenant_id": TENANT,
                    "actor": ACTOR,
                    "tenant_identity_source": "OWNER_ATTESTED",
                    "coverage": "VISIBLE_BOARD_ONLY",
                    "provider_facts": rows,
                    "provider_view_evidence": evidence.view_contract.model_dump(),
                    "derived": {"semantic_board_hash": revision, "load_count": len(rows)},
                    "proposal_state": "UNAPPLIED",
                    "canonical_mutation": False,
                }
                db.execute(
                    "INSERT INTO runtime_proposals VALUES (?,?)",
                    (secrets.token_hex(16), json.dumps(proposal)),
                )
            self.access._audit(
                db,
                "PROPOSAL",
                "BOARD_REFRESHED" if changed else "BOARD_UNCHANGED",
                operation=operation,
                count=len(rows),
            )
            if state["detail_load"] and state["detail_load"] not in {r["load_id"] for r in rows}:
                raise PermissionError("EXACT_LOAD_MISSING")
            state.update(
                board_hash=revision,
                load_count=len(rows),
                last_board_sync=self.clock(),
                step=3 if state["detail_load"] else 0,
                next_due_at=0 if state["detail_load"] else self.clock() + lease["interval_seconds"],
                state="READ_ONLY_READY",
                error_code=None,
            )
            return
        expected = pending["command"]["load_id"]
        if operation == RUNTIME_OPERATIONS[3]:
            evidence = FindEvidence.model_validate(raw)
            evidence.view_contract.require_active()
            if evidence.load_id != expected or evidence.board_hash != state["board_hash"]:
                raise PermissionError("EXACT_LOAD_MISSING")
        elif operation == RUNTIME_OPERATIONS[4]:
            evidence = IdentityEvidence.model_validate(raw)
            evidence.view_contract.require_active()
            if (
                evidence.expected_load_id != expected
                or evidence.observed_load_id != expected
                or evidence.board_hash != state["board_hash"]
            ):
                raise PermissionError("DETAIL_IDENTITY_CONFLICT")
            supported = (
                evidence.detail_field_match
                if evidence.identity_strategy == "PROVIDER_DETAIL_FIELD"
                else evidence.newly_visible
                and evidence.direct_panel_reference
                and (
                    evidence.opener_identity_match
                    if evidence.identity_strategy == "PROVIDER_OPENER_IDENTITY"
                    else evidence.selection_transition
                )
            )
            if not supported:
                raise PermissionError("DETAIL_IDENTITY_MISSING")
            state["identity_verified"] = True
            if state.get("detail_attempt"):
                state["detail_identity"] = evidence.model_dump()
        elif operation == "ASCEND_DISCOVER_DETAIL_CONTRACT":
            try:
                evidence = DetailDiscoveryEvidence.model_validate(raw)
            except ValidationError:
                raise PermissionError("DETAIL_CONTRACT_INVALID") from None
            evidence.view_contract.require_active()
            contract = evidence.contract
            if (not state.get("detail_attempt") or not state["identity_verified"]
                or evidence.load_id != expected or contract.validation_load_id != expected
                or evidence.board_hash != state["board_hash"]
                or contract.identity.model_dump() != state.get("detail_identity")
                or not pending["deadline"] - 12 <= contract.observed_at <= self.clock() + 2):
                raise PermissionError("DETAIL_IDENTITY_CONFLICT")
            latest = db.execute("SELECT body FROM runtime_detail_contracts ORDER BY id DESC LIMIT 1").fetchone()
            previous = json.loads(latest[0]) if latest else None
            fingerprint = contract.contract_fingerprint
            version = 1 if previous is None else previous["contract_version"] + (previous["contract"]["contract_fingerprint"] != fingerprint)
            artifact = {"contract_version": version, "attempt_id": state["detail_attempt"],
                        "received_at": self.clock(), "contract": contract.model_dump(),
                        "previous_fingerprint": previous["contract"]["contract_fingerprint"] if previous else None,
                        "activation": "CANDIDATE_ONLY", "live_validated": False, "production_writes": False}
            db.execute("INSERT INTO runtime_detail_contracts(body) VALUES (?)", (json.dumps(artifact),))
            self.access._audit(db, "RECEIPT", "DETAIL_DISCOVERY_COMPLETE", operation=operation, count=len(contract.fields))
            state.update(state="STOPPED", error_code="DETAIL_DISCOVERY_COMPLETE", detail_load=None,
                         step=0, identity_verified=False, next_due_at=0)
            return
        else:
            evidence = UnknownDetailEvidence.model_validate(raw)
            evidence.view_contract.require_active()
            if (
                not state["identity_verified"]
                or evidence.load_id != expected
                or evidence.board_hash != state["board_hash"]
            ):
                raise PermissionError("DETAIL_IDENTITY_MISSING")
            self.access._audit(db, "RECEIPT", "FIELD_CONTRACT_UNKNOWN", operation=operation)
        state["detail_step"] += 1
        if state["detail_step"] >= 5:
            state.update(
                detail_load=None,
                detail_step=0,
                identity_verified=False,
                step=0,
                next_due_at=self.clock() + lease["interval_seconds"],
            )
