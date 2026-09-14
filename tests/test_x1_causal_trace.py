"""Synthetic causal diagnostic boundaries; no browser or installed native host execution."""

import hashlib
import json
import os
import sqlite3
import subprocess
from uuid import uuid4

import pytest

from executors.ascend_extension.causal_trace import CausalTrace, MAX_EVENTS_PER_JOB, TraceMetadata, emit
from executors.ascend_extension.host import serve
from executors.ascend_extension.native import encode_message
from executors.ascend_extension.workspace_contracts import MappingSessionApproval
from tests.test_ascend_x1_enrollment import enrollment as enrollment, envelope
from tests.test_x1_mapping_notifications import InputPipe, OutputPipe, enrolled_runtime, signed_body


def trace_context():
    state = dict(control_revision=3, document_handshake={
        "tab_id": 7, "document_id": "a" * 32, "document_generation": 2,
        "extension_version": "0.6.4", "service_worker_version": "0.6.4", "content_script_version": "0.6.4",
    })
    lease = dict(generation="b" * 32, mapping=dict(orchestrated=True, causal_trace=True, orchestrator_job_id="c" * 32))
    return state, lease


def trace_body(**changes):
    return dict(kind="RUNTIME_CAUSAL_TRACE", request_id=uuid4().hex, trace={
        "trace_revision": 1, "event": "OWNER_READINESS_PROVED", "tab_id": 7,
        "document_id": "a" * 32, "document_generation": 2, "worker_instance": "d" * 32,
        **changes,
    })


def enable_job(access):
    access.enable(owner_authorized=True, mapping=MappingSessionApproval(
        session_id="owner-x1-mapping-trace-fixture", mode="NORMAL_OWNER_PRESENT", approved_load_ids=["1763"],
        orchestrated=True, causal_trace=True, orchestrator_job_id="c" * 32, capture_load_id="1763", capture_section="Load Basics"))


def records(access):
    with access.database(readonly=True) as db:
        return [json.loads(row[0]) for row in db.execute("SELECT body FROM runtime_causal_events ORDER BY id")]


def test_causal_trace_pseudonymizes_bindings_and_records_fixed_process_metadata():
    state, lease = trace_context()
    with sqlite3.connect(":memory:") as db:
        assert emit(db, state, lease, "OWNER_READINESS_PROVED", metadata={
            "source": "SIGNED_WORKER", "worker_instance": "d" * 32, "owner_present": True, "content_trace_revision": 1, "mapping_reader_revision": 2,
        }, now=1000.25)
        raw = db.execute("SELECT body FROM runtime_causal_events").fetchone()[0]
        evidence = json.loads(raw)
        for value in ["a" * 32, "b" * 32, "c" * 32, "d" * 32]:
            assert value not in raw
        for key, value in [("document_hash", "a"), ("lease_hash", "b"), ("job_hash", "c"), ("worker_instance_hash", "d")]:
            assert evidence[key] == hashlib.sha256((value * 32).encode()).hexdigest()
        assert evidence["tab_id"] == 7 and evidence["document_generation"] == 2
        assert evidence["process_id"] == os.getpid() and len(evidence["runtime_instance"]) == 64
        assert evidence["trace_revision"] == 1 and evidence["controller_revision"] == 3
        assert evidence["content_protocol"] == 3 and evidence["native_protocol"] == 1
        assert evidence["service_worker_version"] == "0.6.4"
        assert evidence["owner_present"] is True and evidence["production_writes"] is False
        assert evidence["content_trace_revision"] == 1
        assert evidence["mapping_reader_revision"] == 2


@pytest.mark.parametrize("value", [0, 3, True, "1", "PRIVATE_VALUE"])
@pytest.mark.parametrize("field", ["content_trace_revision", "mapping_reader_revision"])
def test_content_trace_revision_accepts_only_actual_protocol_revision(field, value):
    from pydantic import ValidationError

    for allowed in [1, 2] if field == "mapping_reader_revision" else [1]:
        assert getattr(CausalTrace(trace_revision=1, event="CONTENT_PORT_PRESENT", **{field: allowed}), field) == allowed
        assert getattr(TraceMetadata(**{field: allowed}), field) == allowed
    with pytest.raises(ValidationError):
        CausalTrace(trace_revision=1, event="CONTENT_PORT_PRESENT", **{field: value})
    with pytest.raises(ValidationError):
        TraceMetadata(**{field: value})


def test_content_protocol_trace_revision_does_not_inherit_mapper_revision():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CausalTrace(trace_revision=1, event="CONTENT_PORT_PRESENT", content_trace_revision=2)
    with pytest.raises(ValidationError):
        TraceMetadata(content_trace_revision=2)


@pytest.mark.parametrize("mutation", ["event", "reason", "raw_metadata", "raw_document", "negative_time", "nan_time"])
def test_causal_trace_refuses_arbitrary_values_and_invalid_shapes(mutation):
    state, lease = trace_context()
    kwargs = dict(event="TAB_BOUND", reason=None, metadata={}, now=1000.0)
    if mutation in {"event", "reason"}:
        kwargs[mutation] = "PRIVATE_VALUE"
    elif mutation == "raw_metadata":
        kwargs["metadata"] = {"html": "PRIVATE_HTML"}
    elif mutation == "raw_document":
        kwargs["metadata"] = {"document_id": "PRIVATE_DOCUMENT"}
    else:
        kwargs["now"] = -1 if mutation == "negative_time" else float("nan")
    with sqlite3.connect(":memory:") as db:
        with pytest.raises(PermissionError, match="^CAUSAL_TRACE_INVALID$"):
            emit(db, state, lease, **kwargs)
        assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='runtime_causal_events'").fetchone()[0] == 0


def test_trace_bound_is_per_job_append_only_and_unrelated_reads_do_not_create_trace():
    state, lease = trace_context()
    with sqlite3.connect(":memory:") as db:
        for unrelated in [None, {}, {"mapping": {}}, {"mapping": {"orchestrated": False}}, {"mapping": {"orchestrated": True}},
            {**lease, "mapping": {**lease["mapping"], "causal_trace": False}}]:
            assert emit(db, state, unrelated, "TAB_BOUND", now=1000) is False
        assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='runtime_causal_events'").fetchone()[0] == 0
        for _ in range(MAX_EVENTS_PER_JOB):
            emit(db, state, lease, "TAB_BOUND", now=1000)
        with pytest.raises(PermissionError, match="CAUSAL_TRACE_BOUND"):
            emit(db, state, lease, "TAB_BOUND", now=1000)
        assert db.execute("SELECT COUNT(*) FROM runtime_causal_events").fetchone()[0] == MAX_EVENTS_PER_JOB
        for statement in ["DELETE FROM runtime_causal_events", "UPDATE runtime_causal_events SET body='{}'"]:
            with pytest.raises(sqlite3.IntegrityError, match="append_only"):
                db.execute(statement)
        other = {**lease, "mapping": {**lease["mapping"], "orchestrator_job_id": "e" * 32}}
        assert emit(db, state, other, "TAB_BOUND", now=1001)


def test_signed_worker_trace_is_bound_to_existing_job_replay_checked_and_no_dispatch(enrollment):
    host, access, package = enrolled_runtime(enrollment)
    enable_job(access)
    before = access.status()
    body = trace_body()
    response = host.handle(envelope(host, package["key"], body))
    receipt = signed_body(response, package["key"])
    assert receipt["kind"] == "RUNTIME_CAUSAL_TRACE_ACK" and receipt["accepted"] is True
    assert receipt["production_writes"] is False and receipt["read_dispatch_enabled"] is False
    evidence = [row for row in records(access) if row["event"] == "OWNER_READINESS_PROVED"][-1]
    assert evidence["source"] == "SIGNED_WORKER" and evidence["document_generation"] == 2
    assert evidence["worker_instance_hash"] == hashlib.sha256(("d" * 32).encode()).hexdigest()
    assert access.status()["mapping_capture_count"] == before["mapping_capture_count"] == 0
    with pytest.raises(PermissionError, match="DUPLICATE_REQUEST"):
        host.handle(envelope(host, package["key"], body, sequence=2))
    with access.database(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM runtime_provider_maps").fetchone()[0] == 0


def test_trace_does_not_enable_or_release_reads_without_an_orchestrated_job(enrollment):
    host, access, package = enrolled_runtime(enrollment)
    receipt = signed_body(host.handle(envelope(host, package["key"], trace_body())), package["key"])
    assert receipt["accepted"] is False
    assert access.status()["read_access"] == "DISABLED"
    with access.database(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM runtime_leases").fetchone()[0] == 0


def test_actual_background_accepts_bound_trace_ack_after_resume_and_revoked_job_wake(enrollment):
    host, access, package = enrolled_runtime(enrollment)
    receipt = signed_body(host.handle(envelope(host, package["key"], trace_body())), package["key"])
    assert receipt["accepted"] is False
    assert {key: receipt[key] for key in ("protocol", "tenant_id", "actor", "state")} == {
        "protocol": 1, "tenant_id": "booking-logistics", "actor": "FreightDesk/Avery", "state": "PAIRED",
    }
    result = subprocess.run(["node", "scripts/check-x1-causal-ack.js"], input=json.dumps(receipt),
        text=True, encoding="utf-8", capture_output=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert access.status()["read_access"] == "DISABLED"


@pytest.mark.parametrize("mutation", ["extra", "private_reason", "host_event", "bad_revision", "boolean_revision"])
def test_native_trace_refuses_untypeable_or_forged_host_events(enrollment, mutation):
    host, access, package = enrolled_runtime(enrollment)
    enable_job(access)
    body = trace_body()
    if mutation == "extra":
        body["trace"]["html"] = "PRIVATE_HTML"
    elif mutation == "private_reason":
        body["trace"]["reason"] = "PRIVATE_ERROR"
    elif mutation == "host_event":
        body["trace"]["event"] = "SIGNED_NOTIFICATION_SENT"
    else:
        body["trace"]["trace_revision"] = True if mutation == "boolean_revision" else 2
    with pytest.raises(PermissionError, match="CAUSAL_TRACE_INVALID"):
        host.handle(envelope(host, package["key"], body))


def test_full_trace_budget_fails_closed_without_preventing_revocation(enrollment):
    host, access, package = enrolled_runtime(enrollment)
    enable_job(access)
    with access.database() as db:
        state, lease = access._load(db)
        emit(db, state, lease, "TAB_BOUND", now=1000)
        existing = db.execute("SELECT COUNT(*) FROM runtime_causal_events").fetchone()[0]
        for _ in range(MAX_EVENTS_PER_JOB-existing):
            emit(db, state, lease, "TAB_BOUND", now=1000)
    with pytest.raises(PermissionError, match="CAUSAL_TRACE_BOUND"):
        host.handle(envelope(host, package["key"], trace_body()))
    assert access.status()["read_access"] == "REVOKED"
    assert access.status()["error_code"] == "CAUSAL_TRACE_BOUND"
    assert len(records(access)) == MAX_EVENTS_PER_JOB


def test_notification_send_receipt_requires_actual_existing_pipe_flush(enrollment):
    import threading

    host, access, package = enrolled_runtime(enrollment)
    enable_job(access)
    access.notify_mapping_job()
    message = host.poll_mapping_notification()
    assert signed_body(message, package["key"])["kind"] == "RUNTIME_JOB_WAKE_NOTIFICATION"
    assert any(row["event"] == "HOST_WAKE_SEEN" for row in records(access))
    assert not any(row["event"] == "SIGNED_NOTIFICATION_SENT" for row in records(access))
    # The polling API alone cannot claim successful transport output.
    host.mark_notification_sent(message)
    assert len([row for row in records(access) if row["event"] == "SIGNED_NOTIFICATION_SENT"]) == 1
    host.mark_notification_sent(message)
    assert len([row for row in records(access) if row["event"] == "SIGNED_NOTIFICATION_SENT"]) == 1
    access.notify_mapping_job()
    source, destination = InputPipe(), OutputPipe()
    worker = threading.Thread(target=lambda: serve(source, destination, host, timeout=3, max_messages=1), daemon=True)
    worker.start()
    try:
        pushed = destination.next_message()
        assert signed_body(pushed, package["key"])["kind"] == "RUNTIME_JOB_WAKE_NOTIFICATION"
        source.feed(encode_message(envelope(host, package["key"], {"kind": "STATUS", "request_id": uuid4().hex})))
        destination.next_message()
        worker.join(timeout=3)
        assert not worker.is_alive()
        events = records(access)
        assert len([row for row in events if row["event"] == "SIGNED_NOTIFICATION_SENT"]) == 2
        assert all(row["production_writes"] is False for row in events)
    finally:
        source.close()
        worker.join(timeout=3)
