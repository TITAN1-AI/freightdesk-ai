"""Bounded stdio host: pairing plus separately granted identity-only reads; operational dispatch closed."""

import os
import queue
import re
import struct
import threading
import time

from pydantic import ValidationError

from executors.ascend_extension.contracts import ReadCommand
from executors.ascend_extension.controller import ReadController, safe_code
from executors.ascend_extension.diagnostics import result_code, validate_metadata
from executors.ascend_extension.enrollment import EnrollmentRepository, PINNED_EXTENSION_ID
from executors.ascend_extension.native import MAX_BYTES, NativeAuthenticator, decode_message, encode_message
from executors.ascend_extension.pairing import ACTOR, PROTOCOL, TENANT, PairingRepository


class HostSession:
    def __init__(
        self,
        repository,
        caller_origin,
        clock=time.time,
        controller=None,
        enrollment_repository=None,
        runtime_controller=None,
    ):
        self.repo, self.origin, self.clock = repository, caller_origin, clock
        self.auth = None
        self.pairing = None
        self.started = clock()
        self.stage = "NATIVE_CONNECT"
        self.flags = {}
        self.reads = controller or ReadController(repository, clock=clock)
        self._enrollments = enrollment_repository
        self.enrollment = None
        self.enrollment_pending = None
        self.resume_pending = None
        self.handshake_deadline = None
        self.runtime = runtime_controller
        self.mapping_notification_sequence = 0
        self.notification_trace_context = None

    def poll_mapping_notification(self):
        """Push only an authenticated wake hint over the existing native pipe.

        The local outbox is observed while stdin is idle; no browser operation, lease,
        or authorization is created here. Signing stays on the host's serving thread.
        """
        if not self.enrollment or not self.auth or not self.auth._authenticated:
            return None
        runtime = self._runtime()
        sequence = runtime.access.mapping_wake_sequence()
        if sequence <= self.mapping_notification_sequence:
            return None
        self._binding()  # Protected identity is rechecked before each notification, not on idle polls.
        from executors.ascend_extension.causal_trace import emit
        with runtime.access.database() as db:
            state, lease = runtime.access._load(db)
            emit(db, state, lease, "HOST_WAKE_SEEN", metadata={"source": "HOST", "notification_sequence": sequence}, now=self.clock())
            self.notification_trace_context = (sequence, state, lease)
        self.mapping_notification_sequence = sequence
        body = dict(kind="RUNTIME_JOB_WAKE_NOTIFICATION", notification_sequence=sequence,
                    protocol=PROTOCOL, tenant_id=TENANT, actor=ACTOR, state="PAIRED",
                    read_dispatch_enabled=False, production_writes=False)
        return {"kind": "AUTHENTICATED", "protocol": PROTOCOL, "envelope": self.auth.sign(body)}

    def mark_notification_sent(self, message):
        """Record a signed hint only after its complete native frame was flushed."""
        context = self.notification_trace_context
        if context is None:
            return
        body = message.get("envelope", {}).get("body", {})
        if body.get("kind") != "RUNTIME_JOB_WAKE_NOTIFICATION" or body.get("notification_sequence") != context[0]:
            raise PermissionError("CAUSAL_TRACE_INVALID")
        from executors.ascend_extension.causal_trace import emit
        runtime = self._runtime()
        with runtime.access.database() as db:
            emit(db, context[1], context[2], "SIGNED_NOTIFICATION_SENT", metadata={"source": "HOST", "notification_sequence": context[0]}, now=self.clock())
        self.notification_trace_context = None

    def _causal_trace(self, body):
        """Accept a strict signed worker diagnostic; it can never become a browser command."""
        from executors.ascend_extension.causal_trace import CausalTraceRequest, emit
        self._enrollment_guard()
        try:
            request = CausalTraceRequest.model_validate(body)
        except ValidationError:
            raise PermissionError("CAUSAL_TRACE_INVALID") from None
        if request.trace.event not in {
            "WORKER_WAKE_RECEIVED", "TAB_CANDIDATE_FOUND", "TAB_BOUND", "CONTENT_PORT_PRESENT",
            "SESSION_PROOF_INVALIDATED", "SESSION_PROOF_INVALIDATION_REASON",
            "OWNER_READINESS_REQUESTED", "OWNER_READINESS_PROVED",
        }:
            raise PermissionError("CAUSAL_TRACE_INVALID")
        runtime = self._runtime()
        try:
            with runtime.access.database() as db:
                runtime._consume(db, request.request_id)
                state, lease = runtime.access._load(db)
                metadata = request.trace.model_dump(exclude={"trace_revision", "event", "reason"}, exclude_none=True)
                accepted = emit(db, state, lease, request.trace.event, request.trace.reason,
                    metadata={**metadata, "source": "SIGNED_WORKER"}, now=self.clock())
        except PermissionError as error:
            if str(error) == "CAUSAL_TRACE_BOUND":
                runtime.invalidate("CAUSAL_TRACE_BOUND")
            raise
        return {"kind": "AUTHENTICATED", "protocol": PROTOCOL, "envelope": self.auth.sign({
            "kind": "RUNTIME_CAUSAL_TRACE_ACK", "trace_revision": 1, "accepted": accepted,
            "protocol": PROTOCOL, "tenant_id": TENANT, "actor": ACTOR, "state": "PAIRED",
            "request_id": request.request_id, "production_writes": False, "read_dispatch_enabled": False,
        })}

    @property
    def enrollments(self):
        # The synthetic process self-test needs only installation/origin validation.
        # Do not construct credential/enrollment dependencies unless that flow is requested.
        if self._enrollments is None:
            self._enrollments = EnrollmentRepository(self.repo)
        return self._enrollments

    def _enrollment_guard(self):
        if not self.enrollment:
            raise PermissionError("not_enrolled")
        return self.enrollments.load(self.enrollment["enrollment_handle"])

    def _runtime(self):
        if self.runtime is None:
            from executors.ascend_extension.runtime import RuntimeController

            self.runtime = RuntimeController(
                self.repo, enrollment_guard=self._enrollment_guard, clock=self.clock
            )
        return self.runtime

    def checkpoint(self, stage, code="PAIRING_HANDSHAKE_PENDING"):
        self.stage = stage
        try:
            self.repo.pairing_audit(dict(self.flags, handshake_stage=stage, result_code=code))
        except Exception:
            raise PermissionError("pairing_persist_failed") from None

    def _binding(self):
        config = self.repo.config()
        if self.origin != f"chrome-extension://{config['extension_id']}/":
            self.flags["extension_id_match"] = False
            raise PermissionError("extension_id_mismatch")
        if self.clock() - self.started > 600:
            raise PermissionError("native_session_expired")
        if self.enrollment:
            self._enrollment_guard()
        if self.pairing:
            self.stage = "DPAPI_VALIDATION"
            if self.repo.load_pairing()["generation"] != self.pairing["generation"]:
                raise PermissionError("stale_pairing")
        return config

    def handle(self, message):
        try:
            return self._handle(message)
        except Exception as error:
            security_errors = {
                "extension_id_mismatch",
                "installation_binding_invalid",
                "unsupported_protocol",
                "enrollment_binding_invalid",
                "enrollment_revoked",
                "enrollment_protection_failed",
                "enrollment_incomplete",
                "native_authentication_or_replay_failure",
                "native_pairing_proof_invalid",
            }
            if error.args and (
                error.args[0] in security_errors
                or error.args[0] == "not_enrolled"
                and self.enrollment is not None
            ):
                try:
                    self.enrollments.revoke(security_mismatch=True)
                except Exception:
                    pass
                try:
                    # Also invalidate an existing lease when a fresh host rejects a mismatch
                    # before it can assign the in-memory enrollment/RESUME state.
                    self._runtime().invalidate("SECURITY_MISMATCH")
                except Exception:
                    # Read guards still fail closed when storage itself is unavailable.
                    pass
                self.auth = None
            if (
                self.enrollment
                or self.resume_pending
                or self.enrollment_pending
                or (
                    isinstance(message, dict)
                    and message.get("kind") in {"ENROLL_HELLO", "ENROLL_PAIR", "RESUME", "RESUME_PROOF"}
                )
            ):
                record = self.enrollment or self.resume_pending or self.enrollment_pending
                try:
                    self.enrollments.audit(
                        record["generation"] if record else "0" * 32, "ENROLLMENT_REJECTED"
                    )
                except Exception:
                    pass
                # A changed installation may prevent the legacy config-bound audit path;
                # do not mask the safe binding failure as a pairing persistence failure.
                raise
            code = result_code(error)
            if code == "PAIRING_EXPIRED":
                self.flags["bootstrap_expired"] = True
            if code == "PAIRING_ALREADY_CONSUMED":
                self.flags["bootstrap_consumed"] = True
            try:
                self.checkpoint(self.stage, code)
            except Exception:
                raise PermissionError("pairing_persist_failed") from None
            raise

    def _handle(self, message):
        config = self._binding()
        if (
            not isinstance(message, dict)
            or message.get("protocol") != PROTOCOL
            or type(message.get("protocol")) is not int
        ):
            raise PermissionError("unsupported_protocol")
        if message.get("kind") in {"ENROLL_HELLO", "ENROLL_PAIR", "RESUME", "RESUME_PROOF"}:
            return self._enrollment_message(message, config)
        if message.get("kind") == "PAIRING_DIAGNOSTIC":
            if set(message) != {"kind", "protocol", "request_id", "diagnostic"}:
                raise PermissionError("malformed_message")
            metadata = validate_metadata(message["diagnostic"])
            if metadata["result_code"] == "PAIRING_SUCCESS" and (
                not self.auth or not self.auth._authenticated
            ):
                raise PermissionError("pairing_required")
            self.repo.consume_request(message["request_id"])
            try:
                self.repo.pairing_audit(metadata)
            except Exception:
                raise PermissionError("pairing_persist_failed") from None
            return {
                "kind": "DIAGNOSTIC_SAVED",
                "protocol": PROTOCOL,
                "result_code": "PAIRING_DIAGNOSTIC_SAVED",
            }
        if message.get("kind") == "HELLO":
            if set(message) != {"kind", "protocol", "request_id"} or self.auth:
                raise PermissionError("malformed_message")
            self.repo.consume_request(message["request_id"])
            self.checkpoint("NATIVE_CONNECT")
            self.stage = "DPAPI_VALIDATION"
            pairing = self.repo.load_pairing()
            self.flags.update(extension_id_match=True, bootstrap_expired=False)
            self.checkpoint("DPAPI_VALIDATION")
            self.flags["bootstrap_consumed"] = self.repo.is_consumed(pairing["generation"])
            self.checkpoint("ONE_TIME_VALIDATION")
            if self.flags["bootstrap_consumed"]:
                raise PermissionError("pairing_already_used")
            self.pairing = pairing
            self.auth = NativeAuthenticator(config["extension_id"], bytes.fromhex(pairing["key"]))
            challenge = self.auth.challenge(self.origin)
            challenge.update(
                installation_id=config["installation_id"], generation=pairing["generation"], protocol=PROTOCOL
            )
            self.repo.audit("CONTROL", "PAIRING_REQUIRED")
            return {"kind": "CHALLENGE", "protocol": PROTOCOL, "challenge": challenge}
        if message.get("kind") == "PAIR":
            if set(message) != {"kind", "protocol", "request_id", "proof"} or not self.auth:
                raise PermissionError("pairing_required")
            self.repo.consume_request(message["request_id"])
            self.checkpoint("PROOF_VALIDATION")
            # Original HMAC challenge binds session + extension + tenant/actor. Installation/generation
            # are additionally bound to the locally protected key and checked against the imported bundle.
            self.auth.authenticate(self.origin, message["proof"])
            self.stage = "PAIRING_PERSIST"
            try:
                self.repo.claim(self.pairing["generation"])
                self.flags["bootstrap_consumed"] = True
                self.repo.audit("CONTROL", "PAIRED")
                self.checkpoint("PAIRING_PERSIST")
            except Exception as error:
                if isinstance(error, PermissionError) and error.args in [
                    ("pairing_already_used",),
                    ("stale_pairing",),
                    ("pairing_expired",),
                ]:
                    raise
                self.flags.pop("bootstrap_consumed", None)
                try:
                    self.flags["bootstrap_consumed"] = self.repo.is_consumed(self.pairing["generation"])
                except Exception:
                    pass
                raise PermissionError("pairing_persist_failed") from None
            self.checkpoint("ACK_VERIFICATION")
            return {
                "kind": "AUTHENTICATED",
                "protocol": PROTOCOL,
                "envelope": self.auth.sign(
                    {
                        "state": "PAIRED",
                        "installation_id": config["installation_id"],
                        "generation": self.pairing["generation"],
                        "protocol": PROTOCOL,
                        "tenant_id": TENANT,
                        "actor": ACTOR,
                        "read_dispatch_enabled": False,
                    }
                ),
            }
        if (
            message.get("kind") != "AUTHENTICATED"
            or set(message) != {"kind", "protocol", "envelope"}
            or not self.auth
        ):
            raise PermissionError("unknown_control_message")
        body = self.auth.verify(self.origin, message["envelope"])
        if body.get("kind") == "RUNTIME_CAUSAL_TRACE":
            return self._causal_trace(body)
        if body.get("kind") in {"RUNTIME_WAKE", "RUNTIME_RESULT", "RUNTIME_STATUS", "RUNTIME_MAPPING_CAPTURE", "RUNTIME_MAPPING_PROGRESS", "RUNTIME_CAPTURE_ACK"}:
            self._enrollment_guard()
            runtime = self._runtime()
            try:
                if body["kind"] == "RUNTIME_WAKE":
                    from executors.ascend_extension.bridge_build import BUILD
                    if body.get("build") != BUILD:
                        raise PermissionError("PROTOCOL_VERSION_MISMATCH")
                    if self.repo.path("mapping-orchestrator.sqlite3").exists():
                        from executors.ascend_extension.mapping_orchestrator import MappingOrchestrator
                        MappingOrchestrator(runtime.access).tick()
                    response = runtime.wake(body)
                elif body["kind"] == "RUNTIME_CAPTURE_ACK":
                    response = runtime.capture_ack(body)
                elif body["kind"] == "RUNTIME_MAPPING_PROGRESS":
                    response = runtime.mapping_progress(body)
                elif body["kind"] == "RUNTIME_RESULT":
                    from executors.ascend_extension.bridge_build import BUILD
                    if body.get("build") != BUILD:
                        raise PermissionError("PROTOCOL_VERSION_MISMATCH")
                    response = runtime.finish(body)
                    if self.repo.path("mapping-orchestrator.sqlite3").exists():
                        from executors.ascend_extension.mapping_orchestrator import MappingOrchestrator
                        MappingOrchestrator(runtime.access).tick()
                        response = runtime.status()
                else:
                    if set(body) != {"kind", "request_id"}:
                        raise PermissionError("malformed_message")
                    self.repo.consume_request(body["request_id"])
                    if body["kind"] == "RUNTIME_MAPPING_CAPTURE":
                        runtime.access.request_mapping_capture(owner_authorized=True)
                    response = runtime.status()
            except PermissionError as error:
                safe_stops = {
                    "PROTOCOL_VERSION_MISMATCH",
                    "READ_ACCESS_DISABLED",
                    "READ_LEASE_EXPIRED",
                    "READ_LEASE_REVOKED",
                    "RUNTIME_PAUSED",
                    "READ_POLICY_BLOCKED",
                    "RUNTIME_SEQUENCE_INVALID",
                }
                from executors.ascend_extension.workspace_contracts import MAPPING_ERRORS
                safe_stops |= MAPPING_ERRORS
                if len(error.args) != 1 or error.args[0] not in safe_stops:
                    raise
                # An owner disable/pause/rebind or expiry can race with a valid in-flight
                # read receipt. Keep transport pairing separate; accept no provider evidence.
                if error.args[0] == "PROTOCOL_VERSION_MISMATCH" and hasattr(runtime, "bridge_failure"):
                    runtime.bridge_failure(error.args[0])
                response = runtime.status()
                response["status"]["error_code"] = error.args[0]
            response.update(
                protocol=PROTOCOL,
                tenant_id=TENANT,
                actor=ACTOR,
                production_writes=False,
                state="PAIRED",
                read_dispatch_enabled=False,
            )
            return {"kind": "AUTHENTICATED", "protocol": PROTOCOL, "envelope": self.auth.sign(response)}
        if body.get("kind") == "STATUS" and set(body) == {"kind", "request_id"}:
            self.repo.consume_request(body["request_id"])
            return {
                "kind": "AUTHENTICATED",
                "protocol": PROTOCOL,
                "envelope": self.auth.sign(
                    {
                        "state": "PAIRED",
                        "read_dispatch_enabled": False,
                        "protocol": PROTOCOL,
                        "tenant_id": TENANT,
                        "actor": ACTOR,
                    }
                ),
            }
        if body.get("kind") in {"READ_PLAN", "READ_REQUEST", "READ_RESULT"}:
            try:
                if body["kind"] == "READ_PLAN":
                    if set(body) != {"kind", "request_id"}:
                        raise PermissionError("COMMAND_NOT_ALLOWED")
                    self.repo.consume_request(body["request_id"])
                    response = {"kind": "READ_PLAN", "plan": self.reads.plan()}
                elif body["kind"] == "READ_REQUEST":
                    response = self.reads.begin(body)
                else:
                    response = {"kind": "READ_RECEIPT", "receipt": self.reads.finish(body)}
            except Exception as error:
                if body.get("kind") == "READ_PLAN":
                    response = {"kind": "READ_ERROR", "error_code": safe_code(error)}
                else:
                    response = {"kind": "READ_RECEIPT", "receipt": self.reads.fail(error)}
            # The global transport flag stays false. Only this signed, single-command grant dispatches.
            response.update(
                state="PAIRED", read_dispatch_enabled=False, protocol=PROTOCOL, tenant_id=TENANT, actor=ACTOR
            )
            return {"kind": "AUTHENTICATED", "protocol": PROTOCOL, "envelope": self.auth.sign(response)}
        command = ReadCommand.model_validate(body)
        self.repo.consume_request(command.request_id)
        self.repo.audit(command.operation, "READ_RELEASE_REQUIRED")
        # The legacy command channel cannot dispatch. Only the separately gated READ_REQUEST path can.
        return {
            "kind": "AUTHENTICATED",
            "protocol": PROTOCOL,
            "envelope": self.auth.sign(
                {
                    "state": "PAIRED",
                    "error_code": "read_release_required",
                    "request_id": command.request_id,
                    "production_writes": False,
                    "read_dispatch_enabled": False,
                }
            ),
        }

    def _enrollment_ack(self):
        record = self._enrollment_guard()
        return {
            "kind": "AUTHENTICATED",
            "protocol": PROTOCOL,
            "envelope": self.auth.sign(
                {
                    "state": "PAIRED",
                    "enrollment": True,
                    "enrollment_handle": record["enrollment_handle"],
                    "generation": record["generation"],
                    "installation_id": record["installation_id"],
                    "protocol": PROTOCOL,
                    "tenant_id": TENANT,
                    "actor": ACTOR,
                    "read_dispatch_enabled": False,
                    "session_expires_at": int(self.started + 600),
                }
            ),
        }

    def _enrollment_message(self, message, config):
        if config["extension_id"] != PINNED_EXTENSION_ID:
            raise PermissionError("extension_id_mismatch")
        kind = message["kind"]
        expected = {"kind", "protocol", "request_id"}
        if kind in {"ENROLL_PAIR", "RESUME_PROOF"}:
            expected.add("proof")
        if kind == "RESUME":
            expected.add("enrollment_handle")
        if set(message) != expected:
            raise PermissionError("malformed_message")
        self.repo.consume_request(message["request_id"])
        if kind in {"ENROLL_HELLO", "RESUME"}:
            if self.auth is not None:
                raise PermissionError("malformed_message")
            self.handshake_deadline = self.clock() + 30
            if kind == "ENROLL_HELLO":
                self.enrollment_pending = self.enrollments.pending()
                record = self.enrollment_pending
                key = bytes.fromhex(record["key"])
            else:
                self.resume_pending = self.enrollments.load(message["enrollment_handle"])
                record = self.resume_pending
                import secrets

                key = secrets.token_bytes(32)
                self.enrollments.audit(record["generation"], "RESUME_CHALLENGE")
            self.auth = NativeAuthenticator(config["extension_id"], key)
            challenge = self.auth.challenge(self.origin)
            challenge.update(installation_id=config["installation_id"], protocol=PROTOCOL)
            if kind == "ENROLL_HELLO":
                challenge["generation"] = record["generation"]
                return {"kind": "CHALLENGE", "protocol": PROTOCOL, "challenge": challenge}
            challenge["enrollment_handle"] = record["enrollment_handle"]
            # This fresh key exists only on the trusted native stdio channel and in memory.
            # The opaque durable handle is not represented as a long-term client secret.
            return {
                "kind": "RESUME_CHALLENGE",
                "protocol": PROTOCOL,
                "session_key": key.hex(),
                "challenge": challenge,
            }
        if self.auth is None or self.handshake_deadline is None or self.clock() >= self.handshake_deadline:
            raise PermissionError("enrollment_challenge_expired")
        if kind == "ENROLL_PAIR":
            if not self.enrollment_pending or self.resume_pending:
                raise PermissionError("pairing_required")
            self.auth.authenticate(self.origin, message["proof"])
            self.enrollment = self.enrollments.claim(self.enrollment_pending["generation"])
            self.enrollment_pending = None
        else:
            if not self.resume_pending or self.enrollment_pending:
                raise PermissionError("pairing_required")
            self.enrollments.load(self.resume_pending["enrollment_handle"])
            self.auth.authenticate(self.origin, message["proof"])
            self.enrollment = self.resume_pending
            self.resume_pending = None
            self.enrollments.audit(self.enrollment["generation"], "RESUME_SUCCESS")
        self.handshake_deadline = None
        return self._enrollment_ack()


SAFE_ERRORS = {
    "extension_id_mismatch",
    "native_session_expired",
    "stale_pairing",
    "pairing_expired",
    "pairing_persist_failed",
    "unsupported_protocol",
    "malformed_message",
    "pairing_required",
    "unknown_control_message",
    "duplicate_request",
    "request_id_invalid",
    "pairing_already_used",
    "native_pairing_proof_invalid",
    "native_pairing_required",
    "native_authentication_or_replay_failure",
    "native_envelope_invalid",
    "native_body_invalid",
    "native_frame_invalid",
    "native_json_invalid",
    "native_shape_invalid",
    "native_message_bound",
    "installation_binding_invalid",
    "pairing_protection_failed",
    "native_read_timeout",
}
SAFE_ERRORS |= {
    "not_enrolled",
    "enrollment_revoked",
    "enrollment_binding_invalid",
    "enrollment_protection_failed",
    "enrollment_bootstrap_expired",
    "enrollment_bootstrap_consumed",
    "enrollment_challenge_expired",
    "enrollment_incomplete",
    "enrollment_device_unavailable",
    "enrollment_handle_invalid",
}


def safe_error(error):
    code = error.args[0] if len(error.args) == 1 and isinstance(error.args[0], str) else None
    if isinstance(error, FileNotFoundError):
        return "PAIRING_REQUIRED", "local_configuration_or_pairing_missing"
    if code in SAFE_ERRORS:
        if code == "not_enrolled":
            return "NOT_ENROLLED", code
        if code.startswith("enrollment_"):
            return "PAIRING_STALE", code
        return (
            "PAIRING_REQUIRED"
            if code
            in {
                "stale_pairing",
                "pairing_expired",
                "pairing_persist_failed",
                "pairing_already_used",
                "pairing_required",
            }
            else "ERROR"
        ), code
    return "ERROR", "invalid_or_unavailable_native_request"


def _read_exact(stream, count):
    chunks = []
    while count:
        part = stream.read(count)
        if not part:
            raise EOFError()
        chunks.append(part)
        count -= len(part)
    return b"".join(chunks)


def receive(stream, timeout=30, *, on_idle=None):
    results = queue.Queue(maxsize=1)

    def reader():
        try:
            prefix = _read_exact(stream, 4)
            (size,) = struct.unpack("<I", prefix)
            if size > MAX_BYTES:
                raise ValueError("native_message_bound")
            results.put((True, decode_message(prefix + _read_exact(stream, size))))
        except Exception as error:
            results.put((False, error))

    threading.Thread(target=reader, daemon=True).start()
    until = time.monotonic() + timeout
    while True:
        remaining = until-time.monotonic()
        if remaining <= 0:
            raise TimeoutError("native_read_timeout") from None
        try:
            ok, value = results.get(timeout=min(0.1, remaining) if on_idle else remaining)
            break
        except queue.Empty:
            if on_idle:
                on_idle()
    if not ok:
        raise value
    return value


def serve(input_stream, output_stream, session, *, timeout=30, max_messages=64, startup=None):
    def notify():
        poll = getattr(session, "poll_mapping_notification", None)
        notification = poll() if poll else None
        if notification is not None:
            output_stream.write(encode_message(notification))
            output_stream.flush()
            mark_sent = getattr(session, "mark_notification_sent", None)
            if mark_sent:
                mark_sent(notification)

    for _ in range(max_messages):
        try:
            message = receive(input_stream, timeout, on_idle=notify)
            if startup:
                startup.record("FIRST_MESSAGE_RECEIVED")
            response = session.handle(message)
        except EOFError:
            if startup:
                startup.record("HOST_EXIT", "HOST_INPUT_CLOSED")
            return
        except Exception as error:
            if startup:
                startup.record(
                    "STARTUP_FAILED",
                    "HOST_REQUEST_REJECTED" if startup.received else "FRAME_READ_FAILED",
                    error,
                )
            state, code = safe_error(error)
            try:
                session.repo.audit("CONTROL", "STOPPED")
            except Exception:
                pass
            output_stream.write(
                encode_message(
                    {
                        "kind": "ERROR",
                        "protocol": PROTOCOL,
                        "state": state,
                        "error_code": code,
                        "result_code": result_code(error),
                    }
                )
            )
            output_stream.flush()
            return  # No retry after malformed, unauthenticated, timeout or uncertain request.
        if startup:
            startup.record("RESPONSE_GENERATED")
        try:
            output_stream.write(encode_message(response))
            output_stream.flush()
        except Exception as error:
            if startup:
                startup.record("STARTUP_FAILED", "STDOUT_WRITE_FAILED", error)
            raise
        if startup:
            startup.record("RESPONSE_FLUSHED")


def main(argv, stdin, stdout, *, startup=None, repository=None):
    if len(argv) not in {1, 2} or not re.fullmatch(r"chrome-extension://[a-p]{32}/", argv[0]):
        stdout.write(
            encode_message(
                {
                    "kind": "ERROR",
                    "protocol": PROTOCOL,
                    "state": "ERROR",
                    "error_code": "extension_id_mismatch",
                }
            )
        )
        stdout.flush()
        return
    self_test = len(argv) == 2 and argv[1] == "--self-test"
    if len(argv) == 2 and not self_test and not re.fullmatch(r"--parent-window=\d+", argv[1]):
        return
    if os.name != "nt":
        return
    session = HostSession(repository or PairingRepository(), argv[0])
    if startup:
        startup.record("HOST_INITIALIZED")
    if self_test:
        # Owner-run process flag only; no bootstrap, DPAPI read, pairing claim or vendor grant.
        session._binding()
        message = receive(stdin, timeout=5)
        if startup:
            startup.record("FIRST_MESSAGE_RECEIVED")
        if message != {"kind": "SELF_TEST_PING", "protocol": 1} or type(message.get("protocol")) is not int:
            raise ValueError("self_test_request_invalid")
        if startup:
            startup.record("RESPONSE_GENERATED", "SELF_TEST_OK")
        stdout.write(
            encode_message(
                {
                    "kind": "SELF_TEST_PONG",
                    "protocol": 1,
                    "production_reads": False,
                    "production_writes": False,
                }
            )
        )
        stdout.flush()
        if startup:
            startup.record("RESPONSE_FLUSHED", "SELF_TEST_OK")
        return
    serve(stdin, stdout, session, startup=startup, timeout=300, max_messages=4096)
