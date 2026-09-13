import hashlib
import hmac
import json
import sqlite3
from uuid import uuid4

import pytest

from executors.ascend_extension.enrollment import EnrollmentRepository, PINNED_EXTENSION_ID
from executors.ascend_extension.host import HostSession, safe_error
from executors.ascend_extension.native import canonical
from executors.ascend_extension.pairing import PairingRepository


@pytest.fixture
def enrollment(tmp_path):
    class Paths:
        def path(self, *parts):
            return tmp_path.joinpath(*parts)

    def protect(data, *, decrypt=False):
        return data[8:] if decrypt else b"FIXTURE:" + data

    now = [1_800_000_000]
    repo = PairingRepository(Paths(), sid=lambda: "fixture-sid", protect=protect, clock=lambda: now[0])
    repo.capture(PINNED_EXTENSION_ID)
    result = EnrollmentRepository(repo, device=lambda: "d" * 64)
    result.test_clock = now
    return result


def request(kind, **extra):
    return {"kind": kind, "protocol": 1, "request_id": uuid4().hex} | extra


def proof(key, challenge):
    signed = {key: challenge[key] for key in ("session_id", "extension_origin", "tenant_id", "actor")}
    return hmac.new(bytes.fromhex(key), canonical(signed), hashlib.sha256).hexdigest()


def new_host(enrollment):
    return HostSession(
        enrollment.repo,
        f"chrome-extension://{PINNED_EXTENSION_ID}/",
        clock=enrollment.clock,
        enrollment_repository=enrollment,
    )


def enroll(enrollment):
    path = enrollment.prepare(owner_authorized=True)
    package = json.loads(path.read_text())
    host = new_host(enrollment)
    challenge = host.handle(request("ENROLL_HELLO"))["challenge"]
    result = host.handle(request("ENROLL_PAIR", proof=proof(package["key"], challenge)))
    return host, result["envelope"]["body"], package


def resume(enrollment, handle):
    host = new_host(enrollment)
    challenge = host.handle(request("RESUME", enrollment_handle=handle))
    result = host.handle(
        request("RESUME_PROOF", proof=proof(challenge["session_key"], challenge["challenge"]))
    )
    return host, result["envelope"]["body"], challenge["session_key"]


def envelope(host, key, body, sequence=1):
    if body.get("kind") in {"RUNTIME_WAKE", "RUNTIME_RESULT"}:
        from executors.ascend_extension.bridge_build import BUILD
        body = {**body, "build": BUILD}
        if body.get("kind") == "RUNTIME_WAKE" and body.get("route"):
            body["handshake"] = {**BUILD, "service_worker_version": BUILD["extension_version"],
                                 "content_script_version": BUILD["extension_version"], "document_generation": 1,
                                 "document_id": body["route"]["document_id"], "tab_id": body["route"]["tab_id"]}
    signed = {
        "session_id": host.auth.session_id,
        "sequence": sequence,
        "direction": "extension_to_host",
        "body": body,
    }
    return {
        "kind": "AUTHENTICATED",
        "protocol": 1,
        "envelope": signed
        | {
            "mac": hmac.new(bytes.fromhex(key), canonical(signed), hashlib.sha256).hexdigest(),
        },
    }


def test_enrollment_explicit_pinned_and_no_implicit_read_release(enrollment):
    with pytest.raises(PermissionError, match="owner_enrollment_required"):
        enrollment.prepare()
    assert enrollment.summary() == {"state": "NOT_ENROLLED", "enrolled": False}
    host, ack, package = enroll(enrollment)
    assert ack["enrollment"] and ack["state"] == "PAIRED"
    assert ack["read_dispatch_enabled"] is False
    assert ack["enrollment_handle"] == enrollment.load()["enrollment_handle"]
    assert package["purpose"] == "X1_ENROLLMENT"
    assert "windows_sid" not in package and "device_identity" not in package
    assert not enrollment.repo.path("enrollment-bootstrap.json").exists()
    assert not enrollment.repo.secret_path().exists()
    manifest = json.loads(enrollment.repo.path("host-manifest.json").read_text())
    assert manifest["allowed_origins"] == [f"chrome-extension://{PINNED_EXTENSION_ID}/"]
    assert "key" not in enrollment.load()
    with pytest.raises(PermissionError, match="enrollment_already_active"):
        enrollment.prepare(owner_authorized=True)
    assert host.pairing is None


@pytest.mark.parametrize("restart", ["popup", "service-worker", "Edge", "Windows", "native-host"])
def test_persistent_reconnect_after_restart_without_bootstrap(enrollment, restart):
    _, ack, package = enroll(enrollment)
    enrollment.test_clock[0] += 86400
    restarted = EnrollmentRepository(enrollment.repo, device=lambda: "d" * 64)
    host, restored, session_key = resume(restarted, ack["enrollment_handle"])
    assert restored["state"] == "PAIRED" and restored["generation"] == ack["generation"]
    assert session_key != package["key"]
    assert (
        host.handle(envelope(host, session_key, {"kind": "STATUS", "request_id": uuid4().hex}))["envelope"][
            "body"
        ]["state"]
        == "PAIRED"
    )
    another, _, next_key = resume(restarted, ack["enrollment_handle"])
    assert another.auth.session_id != host.auth.session_id and next_key != session_key


@pytest.mark.parametrize(
    "field,new",
    [
        ("extension_id", "a" * 32),
        ("installation_id", "b" * 32),
        ("windows_sid", "other-sid"),
        ("protocol", 2),
        ("tenant_id", "other"),
        ("actor", "other"),
    ],
)
def test_binding_change_revokes_enrollment(enrollment, field, new):
    _, ack, _ = enroll(enrollment)
    path = enrollment.repo.path("installation.json")
    config = json.loads(path.read_text())
    config[field] = new
    path.write_text(json.dumps(config))
    with pytest.raises(PermissionError, match="enrollment_binding_invalid"):
        enrollment.load(ack["enrollment_handle"])
    with enrollment.database() as db:
        assert db.execute(
            "SELECT 1 FROM x1_enrollment_events WHERE result_code='SECURITY_MISMATCH'"
        ).fetchone()


def test_device_change_handle_mismatch_and_owner_revoke(enrollment):
    _, ack, _ = enroll(enrollment)
    enrollment.device = lambda: "e" * 64
    with pytest.raises(PermissionError, match="enrollment_binding_invalid"):
        enrollment.load()
    enrollment.device = lambda: "d" * 64
    assert enrollment.summary()["state"] == "PAIRING_STALE"
    enrollment.prepare(owner_authorized=True)
    host = new_host(enrollment)
    package = enrollment.pending()
    challenge = host.handle(request("ENROLL_HELLO"))["challenge"]
    ack = host.handle(request("ENROLL_PAIR", proof=proof(package["key"], challenge)))["envelope"]["body"]
    with pytest.raises(PermissionError, match="enrollment_binding_invalid"):
        enrollment.load("f" * 32)
    assert enrollment.revoke(owner_authorized=True)["state"] == "PAIRING_STALE"
    with pytest.raises(PermissionError, match="enrollment_revoked"):
        enrollment.load(ack["enrollment_handle"])


def test_resume_revocation_between_challenge_and_proof(enrollment):
    _, ack, _ = enroll(enrollment)
    host = new_host(enrollment)
    challenge = host.handle(request("RESUME", enrollment_handle=ack["enrollment_handle"]))
    enrollment.revoke(owner_authorized=True)
    with pytest.raises(PermissionError, match="enrollment_revoked"):
        host.handle(request("RESUME_PROOF", proof=proof(challenge["session_key"], challenge["challenge"])))


def test_resume_challenge_deadline_request_replay_and_old_envelope(enrollment):
    _, ack, _ = enroll(enrollment)
    host = new_host(enrollment)
    first = request("RESUME", enrollment_handle=ack["enrollment_handle"])
    challenge = host.handle(first)
    enrollment.test_clock[0] += 31
    with pytest.raises(PermissionError, match="enrollment_challenge_expired"):
        host.handle(request("RESUME_PROOF", proof=proof(challenge["session_key"], challenge["challenge"])))
    with pytest.raises(PermissionError, match="duplicate_request"):
        new_host(enrollment).handle(first)
    host, _, key = resume(enrollment, ack["enrollment_handle"])
    message = envelope(host, key, {"kind": "STATUS", "request_id": uuid4().hex})
    host.handle(message)
    with pytest.raises(PermissionError, match="native_authentication_or_replay_failure"):
        host.handle(message)
    with pytest.raises(PermissionError, match="enrollment_revoked"):
        enrollment.load()


def test_no_resume_without_verified_proof_no_legacy_enroll(enrollment):
    enrollment.repo.begin_pairing()
    legacy = enrollment.repo.load_pairing()
    host = new_host(enrollment)
    challenge = host.handle(request("HELLO"))["challenge"]
    host.handle(request("PAIR", proof=proof(legacy["key"], challenge)))
    assert enrollment.summary()["state"] == "NOT_ENROLLED"
    with pytest.raises(PermissionError, match="not_enrolled"):
        host.handle(
            envelope(host, legacy["key"], {"kind": "RUNTIME_WAKE", "request_id": uuid4().hex, "route": None})
        )


def test_enrollment_audit_preserves_legacy_history_and_no_secret(enrollment):
    enrollment.repo.consume_request("1" * 32)
    with enrollment.repo.database() as db:
        db.execute("INSERT INTO consumed VALUES ('x1-read','owner-x1-identity-1755-20260911-01')")
    _, ack, package = enroll(enrollment)
    _, _, session_key = resume(enrollment, ack["enrollment_handle"])
    enrollment.revoke(owner_authorized=True)
    with enrollment.database() as db:
        rows = db.execute("SELECT * FROM x1_enrollment_events").fetchall()
        assert db.execute("SELECT COUNT(*) FROM consumed").fetchone()[0] >= 2
        for table in ("x1_enrollment_events", "x1_enrollment_consumed"):
            with pytest.raises(sqlite3.IntegrityError, match="append_only_enrollment_ledger"):
                db.execute(f"DELETE FROM {table}")
    safe = json.dumps(rows)
    for private in (package["key"], session_key, ack["enrollment_handle"], "fixture-sid", "d" * 64):
        assert private not in safe
    assert safe_error(PermissionError("enrollment_revoked")) == ("PAIRING_STALE", "enrollment_revoked")


def test_runtime_commands_are_only_available_after_enrollment(enrollment):
    class Runtime:
        def wake(self, body):
            return {"kind": "RUNTIME_STATUS", "status": {"state": "READ_ACCESS_DISABLED"}}

        def finish(self, body):
            return {"kind": "RUNTIME_STATUS", "status": {"state": "READ_ACCESS_DISABLED"}}

        def status(self):
            return {"kind": "RUNTIME_STATUS", "status": {"state": "READ_ACCESS_DISABLED"}}

    _, ack, _ = enroll(enrollment)
    host, _, key = resume(enrollment, ack["enrollment_handle"])
    host.runtime = Runtime()
    for seq, kind in enumerate(("RUNTIME_WAKE", "RUNTIME_RESULT", "RUNTIME_STATUS"), 1):
        result = host.handle(envelope(host, key, {"kind": kind, "request_id": uuid4().hex}, seq))["envelope"][
            "body"
        ]
        assert result["status"]["state"] == "READ_ACCESS_DISABLED" and result["production_writes"] is False
    with pytest.raises(Exception):
        host.handle(envelope(host, key, {"kind": "SAVE", "request_id": uuid4().hex}, 4))


def test_real_host_runtime_lease_and_revoke_receipt_gate(enrollment):
    from executors.ascend_extension.runtime import RuntimeController

    _, ack, _ = enroll(enrollment)
    host, _, key = resume(enrollment, ack["enrollment_handle"])
    runtime = RuntimeController(
        enrollment.repo, enrollment_guard=host._enrollment_guard, gate=lambda _: None, clock=enrollment.clock
    )
    host.runtime = runtime
    runtime.access.enable(owner_authorized=True)
    route = {
        "tab_id": 7,
        "document_id": "b" * 32,
        "eligible_tab_count": 1,
        "origin": "https://ascendtms.com",
        "path": "/loads",
    }
    response = host.handle(
        envelope(host, key, {"kind": "RUNTIME_WAKE", "request_id": uuid4().hex, "route": route})
    )["envelope"]["body"]
    assert response["kind"] == "RUNTIME_DISPATCH"
    assert response["command"]["operation"] == "ASCEND_GET_SESSION_STATE"
    assert response["state"] == "PAIRED" and response["read_dispatch_enabled"] is False
    enrollment.revoke(owner_authorized=True)
    result = {
        "kind": "RUNTIME_RESULT",
        "request_id": uuid4().hex,
        "command_request_id": response["command"]["request_id"],
        "route": route,
        "evidence": {
            "authenticated_app": True,
            "login_form_present": False,
            "nav_markers": ["Dashboard", "Loads", "Customers", "Carriers"],
        },
        "error_code": None,
    }
    with pytest.raises(PermissionError, match="enrollment_revoked"):
        host.handle(envelope(host, key, result, 2))
    assert runtime.access.status()["read_access"] == "REVOKED"
    with runtime.access.database(readonly=True) as db:
        state, _ = runtime.access._load(db)
        assert state["pending"] is None
        assert db.execute("SELECT COUNT(*) FROM runtime_proposals").fetchone()[0] == 0


@pytest.mark.parametrize("mismatch", ["origin", "protocol", "configuration", "handle", "manifest"])
def test_fresh_host_security_mismatch_persistently_revokes_old_lease(enrollment, mismatch):
    from executors.ascend_extension.runtime import RuntimeAccess

    _, ack, _ = enroll(enrollment)
    access = RuntimeAccess(
        enrollment.repo,
        enrollment_guard=lambda: enrollment.load(),
        gate=lambda _: None,
        clock=enrollment.clock,
    )
    access.enable(owner_authorized=True)
    host = new_host(enrollment)
    raw = request("RESUME", enrollment_handle=ack["enrollment_handle"])
    restore = None
    if mismatch == "origin":
        host.origin = "chrome-extension://" + "a" * 32 + "/"
    elif mismatch == "protocol":
        raw["protocol"] = 2
    elif mismatch == "handle":
        raw["enrollment_handle"] = "f" * 32
    else:
        path = enrollment.repo.path(
            "installation.json" if mismatch == "configuration" else "host-manifest.json"
        )
        before = path.read_text()
        value = json.loads(before)
        value.update(
            {"installation_id": "e" * 32}
            if mismatch == "configuration"
            else {"allowed_origins": ["chrome-extension://*/"]}
        )
        path.write_text(json.dumps(value))
        restore = (path, before)
    with pytest.raises(PermissionError):
        host.handle(raw)
    if restore:
        restore[0].write_text(restore[1])
    assert access.status()["read_access"] == "REVOKED"
    with pytest.raises(PermissionError, match="enrollment_revoked"):
        enrollment.load(ack["enrollment_handle"])


def test_existing_explicit_owner_reset_revokes_persistent_enrollment_and_lease(enrollment):
    from executors.ascend_extension.runtime import RuntimeAccess

    _, ack, _ = enroll(enrollment)
    access = RuntimeAccess(
        enrollment.repo,
        enrollment_guard=lambda: enrollment.load(),
        gate=lambda _: None,
        clock=enrollment.clock,
    )
    access.enable(owner_authorized=True)
    enrollment.repo.consume_request("1" * 32)
    enrollment.repo.reset()
    assert access.status()["read_access"] == "REVOKED"
    with pytest.raises(PermissionError, match="enrollment_revoked"):
        enrollment.load(ack["enrollment_handle"])
    with pytest.raises(PermissionError, match="duplicate_request"):
        enrollment.repo.consume_request("1" * 32)


def test_initial_enrollment_bootstrap_expiry_and_replay_are_bounded(enrollment):
    enrollment.prepare(owner_authorized=True)
    enrollment.test_clock[0] += 601
    with pytest.raises(PermissionError, match="enrollment_bootstrap_expired"):
        new_host(enrollment).handle(request("ENROLL_HELLO"))
    enrollment.prepare(owner_authorized=True)
    pending = enrollment.pending()
    host = new_host(enrollment)
    challenge = host.handle(request("ENROLL_HELLO"))["challenge"]
    proof_message = request("ENROLL_PAIR", proof=proof(pending["key"], challenge))
    host.handle(proof_message)
    with pytest.raises(PermissionError, match="duplicate_request"):
        host.handle(proof_message)
    with pytest.raises(PermissionError, match="not_enrolled"):
        new_host(enrollment).handle(request("ENROLL_HELLO"))


def test_old_resume_proof_cannot_authenticate_another_host_session(enrollment):
    _, ack, _ = enroll(enrollment)
    first = new_host(enrollment)
    response = first.handle(request("RESUME", enrollment_handle=ack["enrollment_handle"]))
    old_proof = proof(response["session_key"], response["challenge"])
    second = new_host(enrollment)
    second.handle(request("RESUME", enrollment_handle=ack["enrollment_handle"]))
    with pytest.raises(PermissionError, match="native_pairing_proof_invalid"):
        second.handle(request("RESUME_PROOF", proof=old_proof))
    assert enrollment.summary()["state"] == "PAIRING_STALE"


@pytest.mark.parametrize("owner_action", ["disable", "pause", "rebind", "expiry"])
def test_inflight_owner_lease_stop_does_not_break_verified_pairing(enrollment, owner_action):
    from executors.ascend_extension.runtime import RuntimeController

    _, ack, _ = enroll(enrollment)
    host, _, key = resume(enrollment, ack["enrollment_handle"])
    host.runtime = RuntimeController(
        enrollment.repo, enrollment_guard=host._enrollment_guard, gate=lambda _: None, clock=enrollment.clock
    )
    access = host.runtime.access
    access.enable(owner_authorized=True, hours=1 / 60)
    route = {
        "tab_id": 7,
        "document_id": "b" * 32,
        "eligible_tab_count": 1,
        "origin": "https://ascendtms.com",
        "path": "/loads",
    }
    dispatched = host.handle(
        envelope(host, key, {"kind": "RUNTIME_WAKE", "request_id": uuid4().hex, "route": route})
    )["envelope"]["body"]
    if owner_action == "disable":
        access.disable(owner_authorized=True)
    elif owner_action == "pause":
        access.set_paused(True, owner_authorized=True)
    elif owner_action == "rebind":
        access.request_rebind(owner_authorized=True)
    else:
        enrollment.test_clock[0] += 61
    receipt = {
        "kind": "RUNTIME_RESULT",
        "request_id": uuid4().hex,
        "command_request_id": dispatched["command"]["request_id"],
        "route": route,
        "evidence": {
            "authenticated_app": True,
            "login_form_present": False,
            "nav_markers": ["Dashboard", "Loads", "Customers", "Carriers"],
        },
        "error_code": None,
    }
    result = host.handle(envelope(host, key, receipt, 2))["envelope"]["body"]
    assert result["kind"] == "RUNTIME_STATUS" and result["state"] == "PAIRED"
    assert result["status"]["error_code"] in {
        "READ_LEASE_REVOKED",
        "RUNTIME_PAUSED",
        "RUNTIME_SEQUENCE_INVALID",
        "READ_LEASE_EXPIRED",
    }
    assert enrollment.summary()["enrolled"] is True
    with access.database(readonly=True) as db:
        assert db.execute("SELECT COUNT(*) FROM runtime_proposals").fetchone()[0] == 0
