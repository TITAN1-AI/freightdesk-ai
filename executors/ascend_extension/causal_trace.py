"""Bounded causal metadata for one orchestrated mapping job; never provider values."""

import hashlib
import json
import math
import os
import re
import secrets
from typing import Literal

from pydantic import Field, ValidationError, field_validator

from executors.ascend_extension.bridge_build import BUILD
from executors.ascend_extension.controller import Strict

TRACE_REVISION = 1
MAX_EVENTS_PER_JOB = 256
RUNTIME_INSTANCE = hashlib.sha256(secrets.token_bytes(32)).hexdigest()

Event = Literal[
    "JOB_COMMITTED", "WAKE_WRITTEN", "HOST_WAKE_SEEN", "SIGNED_NOTIFICATION_SENT",
    "WORKER_WAKE_RECEIVED", "TAB_CANDIDATE_FOUND", "TAB_BOUND", "CONTENT_PORT_PRESENT",
    "SESSION_PROOF_REQUESTED", "SESSION_PROOF_SUCCEEDED", "SESSION_PROOF_INVALIDATED",
    "SESSION_PROOF_INVALIDATION_REASON", "OWNER_READINESS_REQUESTED", "OWNER_READINESS_PROVED",
    "CAPTURE_QUEUED", "CAPTURE_DISPATCH_ATTEMPTED", "CAPTURE_DISPATCHED", "CAPTURE_ACKNOWLEDGED",
]
Reason = Literal[
    "TAB_SELECTION_CHANGED", "DOCUMENT_ID_CHANGED", "DOCUMENT_GENERATION_CHANGED",
    "CONTENT_PATH_CHANGED", "CONTENT_PORT_REPLACED", "CONTENT_PORT_DISCONNECTED",
    "ROUTER_REBOUND", "FOREGROUND_LOST", "FOCUS_LOST", "HOST_GENERATION_CHANGED",
    "LEASE_GENERATION_CHANGED", "CONTENT_READY_MISMATCH", "ROUTING_PATH_CHANGED",
    "DOCUMENT_LOADING", "READINESS_BINDING_CHANGED", "SESSION_RECEIPT_EXPIRED",
    "DOCUMENT_CHANGED", "TAB_STATE_CHANGED", "TAB_SELECTION_REQUIRED", "TAB_DISCOVERY_FAILED",
    "SESSION_UNVERIFIED", "ASCEND_REAUTH_REQUIRED", "LEASE_REVOKED", "OWNER_NOT_PRESENT",
    "READ_TIMEOUT", "ROUTING_PROOF_INVALIDATED",
    "CONTENT_SCRIPT_MISSING", "CONTENT_SCRIPT_OLD_VERSION", "CONTENT_SCRIPT_PORT_STALE",
    "PROTOCOL_VERSION_MISMATCH", "CONTENT_SCRIPT_INJECTION_BLOCKED", "CONTENT_SCRIPT_RECOVERY_FAILED",
    "READ_EXECUTION_FAILED", "READ_POLICY_BLOCKED", "NO_FOREGROUND_ASCEND_WORKSPACE",
]


class CausalTrace(Strict):
    trace_revision: Literal[1]
    event: Event
    reason: Reason | None = None
    tab_id: int | None = Field(default=None, ge=0, le=2147483647)
    document_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    document_generation: int | None = Field(default=None, ge=1, le=1000000)
    worker_instance: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    content_trace_revision: Literal[1] | None = None
    mapping_reader_revision: Literal[1, 2] | None = None

    @field_validator("trace_revision", mode="before")
    @classmethod
    def exact_revision_type(cls, value):
        if type(value) is not int:
            raise ValueError("CAUSAL_TRACE_INVALID")
        return value

    @field_validator("content_trace_revision", "mapping_reader_revision", mode="before")
    @classmethod
    def exact_content_revision_type(cls, value):
        if value is not None and type(value) is not int:
            raise ValueError("CAUSAL_TRACE_INVALID")
        return value


class CausalTraceRequest(Strict):
    kind: Literal["RUNTIME_CAUSAL_TRACE"]
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    trace: CausalTrace


class TraceMetadata(Strict):
    source: Literal["LOCAL_EXECUTOR", "COORDINATOR", "HOST", "SIGNED_WORKER"] = "LOCAL_EXECUTOR"
    tab_id: int | None = Field(default=None, ge=0, le=2147483647)
    document_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    document_generation: int | None = Field(default=None, ge=1, le=1000000)
    worker_instance: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    content_trace_revision: Literal[1] | None = None
    mapping_reader_revision: Literal[1, 2] | None = None
    notification_sequence: int | None = Field(default=None, ge=1, le=9007199254740991)
    eligible_tab_count: int | None = Field(default=None, ge=0, le=100)
    owner_present: bool | None = None
    probe_only: bool | None = None
    control_revision: int | None = Field(default=None, ge=0, le=1000000000)

    @field_validator("content_trace_revision", "mapping_reader_revision", mode="before")
    @classmethod
    def exact_content_revision_type(cls, value):
        if value is not None and type(value) is not int:
            raise ValueError("CAUSAL_TRACE_INVALID")
        return value


def _hash(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def ensure_schema(db):
    db.execute("CREATE TABLE IF NOT EXISTS runtime_causal_events(id INTEGER PRIMARY KEY,body TEXT NOT NULL)")
    for operation in ("UPDATE", "DELETE"):
        db.execute(
            f"CREATE TRIGGER IF NOT EXISTS runtime_causal_events_no_{operation} BEFORE {operation} ON runtime_causal_events "
            "BEGIN SELECT RAISE(ABORT, 'append_only_runtime_history'); END"
        )


def emit(db, state, lease, event, reason=None, metadata=None, now=None):
    """Append safe metadata inside the caller's existing runtime transaction.

    Inactive/unrelated runtime traffic does not create a trace. Diagnostic receipts never
    grant authority, load credentials, dispatch a browser operation or mutate provider data.
    Document/lease/job/worker identities are pseudonymized before persistence.
    """
    mapping = lease.get("mapping") if isinstance(lease, dict) else None
    if (not isinstance(mapping, dict) or mapping.get("orchestrated") is not True
        or mapping.get("causal_trace") is not True):
        return False
    job_id = mapping.get("orchestrator_job_id")
    generation = lease.get("generation")
    if not isinstance(job_id, str) or not re.fullmatch(r"[a-f0-9]{32}", job_id):
        return False
    if not isinstance(generation, str) or not re.fullmatch(r"[a-f0-9]{32}", generation):
        raise PermissionError("CAUSAL_TRACE_INVALID")
    try:
        CausalTrace(trace_revision=TRACE_REVISION, event=event, reason=reason)
        safe = TraceMetadata.model_validate(metadata or {})
    except (ValidationError, TypeError):
        raise PermissionError("CAUSAL_TRACE_INVALID") from None
    if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
        raise PermissionError("CAUSAL_TRACE_INVALID")
    handshake = state.get("document_handshake") or {}
    route = state.get("route") or {}
    # Existing proof objects already have a strict schema; revalidate identities before hashing.
    document = safe.document_id if safe.document_id is not None else handshake.get("document_id", route.get("document_id"))
    if document is not None and (not isinstance(document, str) or not re.fullmatch(r"[a-f0-9]{32}", document)):
        raise PermissionError("CAUSAL_TRACE_INVALID")
    tab_id = safe.tab_id if safe.tab_id is not None else handshake.get("tab_id", route.get("tab_id"))
    document_generation = safe.document_generation if safe.document_generation is not None else handshake.get("document_generation")
    try:
        binding = TraceMetadata(tab_id=tab_id, document_generation=document_generation)
    except ValidationError:
        raise PermissionError("CAUSAL_TRACE_INVALID") from None
    job_hash = _hash(job_id)
    ensure_schema(db)
    count = db.execute("SELECT COUNT(*) FROM runtime_causal_events WHERE json_extract(body,'$.job_hash')=?", (job_hash,)).fetchone()[0]
    if count >= MAX_EVENTS_PER_JOB:
        raise PermissionError("CAUSAL_TRACE_BOUND")
    record = dict(
        trace_revision=TRACE_REVISION, event=event, reason=reason, observed_at=now,
        job_hash=job_hash, lease_hash=_hash(generation),
        document_hash=_hash(document) if document is not None else None,
        worker_instance_hash=_hash(safe.worker_instance) if safe.worker_instance is not None else None,
        tab_id=binding.tab_id, document_generation=binding.document_generation,
        source=safe.source, process_id=os.getpid(), runtime_instance=RUNTIME_INSTANCE,
        control_revision=safe.control_revision if safe.control_revision is not None else state.get("control_revision") if type(state.get("control_revision")) is int else None,
        native_protocol=BUILD["native_protocol"], controller_revision=BUILD["controller_revision"],
        content_protocol=BUILD["content_protocol"], extension_version=BUILD["extension_version"],
        document_receipt_present=bool(handshake),
        notification_sequence=safe.notification_sequence, eligible_tab_count=safe.eligible_tab_count,
        owner_present=safe.owner_present, probe_only=safe.probe_only, production_writes=False,
        content_trace_revision=safe.content_trace_revision,
        mapping_reader_revision=safe.mapping_reader_revision,
    )
    for field in ("service_worker_version", "content_script_version"):
        record[field] = handshake.get(field) if handshake.get(field) == BUILD["extension_version"] else None
    db.execute("INSERT INTO runtime_causal_events(body) VALUES (?)", (json.dumps(record),))
    return True
