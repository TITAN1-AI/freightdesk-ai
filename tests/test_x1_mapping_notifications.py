"""Existing-pipe mapping wake tests; synthetic enrollment and in-memory streams only."""
import hashlib
import hmac
import io
import queue
import sqlite3
import threading
from uuid import uuid4

import pytest

from executors.ascend_extension.host import HostSession, receive, serve
from executors.ascend_extension.native import canonical, decode_message, encode_message
from executors.ascend_extension.runtime import RuntimeAccess, RuntimeController
from tests.test_ascend_x1_controller import repo as repo
from tests.test_ascend_x1_enrollment import enrollment as enrollment, enroll, envelope
from tests.test_ascend_x1_runtime import runtime as runtime


class InputPipe:
    """A blocking byte stream with deterministic input delivery, never a process pipe."""

    def __init__(self):
        self.chunks = queue.Queue()
        self.buffer = bytearray()
        self.closed = False

    def read(self, size):
        while len(self.buffer) < size and not self.closed:
            part = self.chunks.get(timeout=5)
            if part is None:
                self.closed = True
            else:
                self.buffer.extend(part)
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        return result

    def feed(self, value):
        self.chunks.put(value)

    def close(self):
        self.chunks.put(None)


class OutputPipe:
    def __init__(self):
        self.frames = queue.Queue()
        self.flush_count = 0

    def write(self, value):
        self.frames.put(value)
        return len(value)

    def flush(self):
        self.flush_count += 1

    def next_message(self):
        return decode_message(self.frames.get(timeout=3))


def signed_body(message, key):
    assert message["kind"] == "AUTHENTICATED"
    signed = {key: value for key, value in message["envelope"].items() if key != "mac"}
    expected = hmac.new(bytes.fromhex(key), canonical(signed), hashlib.sha256).hexdigest()
    assert hmac.compare_digest(expected, message["envelope"]["mac"])
    assert signed["direction"] == "host_to_extension"
    return signed["body"]


def enrolled_runtime(enrollment):
    host, _, package = enroll(enrollment)
    kwargs = dict(enrollment_guard=enrollment.load, gate=lambda _: None, clock=enrollment.clock)
    access = RuntimeAccess(enrollment.repo, **kwargs)
    host.runtime = RuntimeController(enrollment.repo, **kwargs)
    return host, access, package


def test_mapping_wake_outbox_is_durable_append_only_and_not_authority(runtime):
    access, _, now, *_ = runtime
    access.enrollment_guard = lambda: pytest.fail("Wake hint must not load protected enrollment")
    access.gate = lambda _: pytest.fail("Wake hint must not request read execution")
    assert access.mapping_wake_sequence() == 0
    assert not access.path.exists()
    access.notify_mapping_job()
    now[0] += 1
    access.notify_mapping_job()
    assert access.mapping_wake_sequence() == 2
    assert access.status()["read_access"] == "DISABLED"
    with access.database(readonly=True) as db:
        assert db.execute("SELECT created_at FROM runtime_mapping_wakes ORDER BY id").fetchall() == [(1000.0,), (1001.0,)]
        for table in ["runtime_leases", "runtime_receipts", "runtime_events", "runtime_provider_maps"]:
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    with access.database() as db:
        with pytest.raises(sqlite3.IntegrityError, match="append_only"):
            db.execute("DELETE FROM runtime_mapping_wakes")


@pytest.mark.parametrize("incomplete_state", ["none", "enrollment_only", "auth_only", "unauthenticated"])
def test_no_notification_dependencies_before_verified_enrollment(repo, monkeypatch, incomplete_state):
    host = HostSession(repo, "chrome-extension://"+"a"*32+"/")
    if incomplete_state in {"enrollment_only", "unauthenticated"}:
        host.enrollment = {"fixture": True}
    if incomplete_state in {"auth_only", "unauthenticated"}:
        class Auth:
            _authenticated = incomplete_state == "auth_only"
        host.auth = Auth()
    monkeypatch.setattr(host, "_binding", lambda: pytest.fail("No protected binding load before enrollment"))
    monkeypatch.setattr(host, "_runtime", lambda: pytest.fail("No runtime lookup before enrollment"))
    assert host.poll_mapping_notification() is None
    assert host.mapping_notification_sequence == 0


def test_authenticated_notification_coalesces_and_deduplicates_without_read_grant(enrollment):
    host, access, package = enrolled_runtime(enrollment)
    access.notify_mapping_job()
    access.notify_mapping_job()
    first = host.poll_mapping_notification()
    body = signed_body(first, package["key"])
    assert body == dict(kind="RUNTIME_JOB_WAKE_NOTIFICATION", notification_sequence=2, protocol=1,
        tenant_id="booking-logistics", actor="FreightDesk/Avery", state="PAIRED", read_dispatch_enabled=False, production_writes=False)
    outgoing = host.auth._outgoing
    assert host.poll_mapping_notification() is None
    assert host.auth._outgoing == outgoing
    access.notify_mapping_job()
    assert signed_body(host.poll_mapping_notification(), package["key"])["notification_sequence"] == 3
    assert access.status()["read_access"] == "DISABLED"
    with access.database(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM runtime_leases").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM runtime_requests").fetchone()[0] == 0


def test_notification_rechecks_binding_before_signing(enrollment):
    host, access, _ = enrolled_runtime(enrollment)
    access.notify_mapping_job()
    host.origin = "chrome-extension://"+"a"*32+"/"
    outgoing = host.auth._outgoing
    with pytest.raises(PermissionError, match="extension_id_mismatch"):
        host.poll_mapping_notification()
    assert host.mapping_notification_sequence == 0
    assert host.auth._outgoing == outgoing


def test_receive_idle_callback_does_not_consume_or_change_frame():
    stream = InputPipe()
    counts = []
    payload = {"kind": "SYNTHETIC_ONLY", "count": 1}
    def on_idle():
        counts.append(True)
        stream.feed(encode_message(payload))
    try:
        assert receive(stream, timeout=2, on_idle=on_idle) == payload
        assert counts == [True]
        assert receive(io.BytesIO(encode_message(payload)), on_idle=lambda: pytest.fail("Complete frame needs no idle polling")) == payload
    finally:
        stream.close()


def test_serve_pushes_signed_wake_on_idle_existing_pipe_before_any_request(enrollment):
    host, access, package = enrolled_runtime(enrollment)
    source, destination = InputPipe(), OutputPipe()
    access.notify_mapping_job()
    failures = []
    def run():
        try:
            serve(source, destination, host, timeout=3, max_messages=1)
        except Exception as error:
            failures.append(type(error).__name__)
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    try:
        # The owner-local job sends an outbox hint; no incoming heartbeat or runtime wake is fed.
        first = destination.next_message()
        assert signed_body(first, package["key"])["kind"] == "RUNTIME_JOB_WAKE_NOTIFICATION"
        assert destination.flush_count == 1
        request = envelope(host, package["key"], {"kind": "STATUS", "request_id": uuid4().hex})
        source.feed(encode_message(request))
        second = destination.next_message()
        assert signed_body(second, package["key"])["state"] == "PAIRED"
        assert second["envelope"]["sequence"] == first["envelope"]["sequence"] + 1
        worker.join(timeout=3)
        assert not worker.is_alive() and failures == []
        assert destination.frames.empty() and destination.flush_count == 2
        assert access.status()["read_access"] == "DISABLED"
        with access.database(readonly=True) as db:
            assert db.execute("SELECT COUNT(*) FROM runtime_leases").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM runtime_provider_maps").fetchone()[0] == 0
    finally:
        source.close()
        worker.join(timeout=3)
