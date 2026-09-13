"""Owner-enrolled, DPAPI-bound local identity; no browser/network/registry writes.

Reconnect authentication relies on Edge's exact Native Messaging origin and the protected
Windows-local enrollment. The extension retains only an opaque handle. This does not claim
protection from malicious code already executing as the enrolled Windows user.
"""

import hashlib
import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from executors.ascend_extension.pairing import HOST_NAME


PINNED_EXTENSION_ID = "opckmnldaebecjphbmdmelfflikinpif"
PURPOSE = "X1_ENROLLMENT"
HEX32 = re.compile(r"[a-f0-9]{32}")
SAFE_CODES = frozenset(
    {
        "ENROLLMENT_PREPARED",
        "ENROLLMENT_SUCCESS",
        "RESUME_CHALLENGE",
        "RESUME_SUCCESS",
        "OWNER_REVOKED",
        "SECURITY_MISMATCH",
        "ENROLLMENT_REJECTED",
    }
)


def windows_device_identity() -> str:
    """Read the Windows installation identity only when explicitly used by local runtime."""
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Cryptography",
        0,
        winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
    ) as key:
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
    if not isinstance(value, str) or not value.strip():
        raise PermissionError("enrollment_device_unavailable")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class EnrollmentRepository:
    def __init__(self, repository, *, device=windows_device_identity):
        self.repo = repository
        self.clock = repository.clock
        self.device = device

    def _secret(self, name):
        return self.repo.paths.path("Secrets", name)

    def _read(self, name):
        try:
            raw = self.repo.protect(self._secret(name).read_bytes(), decrypt=True)
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except FileNotFoundError:
            raise PermissionError("not_enrolled") from None
        except Exception:
            raise PermissionError("enrollment_protection_failed") from None

    def _write(self, name, value):
        target = self._secret(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        pending = self._secret(name + ".pending")
        pending.write_bytes(self.repo.protect(json.dumps(value, sort_keys=True).encode()))
        pending.replace(target)

    def _binding(self):
        config = self.repo.config()
        if config["extension_id"] != PINNED_EXTENSION_ID:
            raise PermissionError("extension_id_mismatch")
        manifest = json.loads(self.repo.path("host-manifest.json").read_text(encoding="utf-8"))
        if (
            manifest.get("allowed_origins") != [f"chrome-extension://{PINNED_EXTENSION_ID}/"]
            or manifest.get("name") != HOST_NAME
            or manifest.get("type") != "stdio"
            or manifest.get("path") != str(self.repo.path("FreightDeskAscendHost.exe"))
        ):
            raise PermissionError("enrollment_binding_invalid")
        device = self.device()
        if not isinstance(device, str) or not re.fullmatch(r"[a-f0-9]{64}", device):
            raise PermissionError("enrollment_device_unavailable")
        return {
            key: config[key]
            for key in ("extension_id", "installation_id", "windows_sid", "protocol", "tenant_id", "actor")
        } | {"device_identity": device}

    @contextmanager
    def database(self):
        # Paths still reject reparse points. Security invalidation remains possible after a
        # changed installation binding, without rewriting any legacy grant/audit table.
        db = sqlite3.connect(self.repo.path("bridge.sqlite3"), timeout=2)
        db.execute(
            "CREATE TABLE IF NOT EXISTS x1_enrollment_events (timestamp TEXT, generation TEXT, result_code TEXT)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS x1_enrollment_consumed (kind TEXT, id TEXT, PRIMARY KEY(kind,id))"
        )
        for table in ("x1_enrollment_events", "x1_enrollment_consumed"):
            for operation in ("UPDATE", "DELETE"):
                db.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation} BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT, 'append_only_enrollment_ledger'); END"
                )
        try:
            with db:
                yield db
        finally:
            db.close()

    def _audit(self, db, generation, code):
        if not isinstance(generation, str) or not HEX32.fullmatch(generation) or code not in SAFE_CODES:
            raise PermissionError("enrollment_audit_invalid")
        db.execute(
            "INSERT INTO x1_enrollment_events VALUES (?,?,?)",
            (
                datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(),
                generation,
                code,
            ),
        )

    def audit(self, generation, code):
        with self.database() as db:
            self._audit(db, generation, code)

    def _revoked(self, db, generation):
        return (
            db.execute(
                "SELECT 1 FROM x1_enrollment_events WHERE generation=? AND result_code IN ('OWNER_REVOKED','SECURITY_MISMATCH')",
                (generation,),
            ).fetchone()
            is not None
        )

    def prepare(self, *, owner_authorized=False):
        if owner_authorized is not True:
            raise PermissionError("owner_enrollment_required")
        binding = self._binding()
        try:
            self.load()
        except PermissionError as error:
            if error.args[0] not in {"not_enrolled", "enrollment_revoked", "enrollment_binding_invalid"}:
                raise
        else:
            raise PermissionError("enrollment_already_active")
        pending = binding | {
            "generation": secrets.token_hex(16),
            "key": secrets.token_hex(32),
            "expires_at": int(self.clock() + 600),
            "purpose": PURPOSE,
        }
        self._write("ascend-x1-enrollment-pending.dpapi", pending)
        package = {
            key: value for key, value in pending.items() if key not in {"windows_sid", "device_identity"}
        }
        path = self.repo.path("enrollment-bootstrap.json")
        path.write_text(json.dumps(package), encoding="utf-8")
        self.audit(pending["generation"], "ENROLLMENT_PREPARED")
        return path

    def pending(self):
        data = self._read("ascend-x1-enrollment-pending.dpapi")
        binding = self._binding()
        if (
            set(data) != set(binding) | {"generation", "key", "expires_at", "purpose"}
            or any(data.get(key) != value for key, value in binding.items())
            or data.get("purpose") != PURPOSE
            or type(data.get("expires_at")) is not int
            or type(data.get("protocol")) is not int
            or not HEX32.fullmatch(str(data.get("generation", "")))
            or not re.fullmatch(r"[a-f0-9]{64}", str(data.get("key", "")))
        ):
            raise PermissionError("enrollment_binding_invalid")
        if not self.clock() < data["expires_at"] <= self.clock() + 601:
            raise PermissionError("enrollment_bootstrap_expired")
        with self.database() as db:
            if db.execute(
                "SELECT 1 FROM x1_enrollment_consumed WHERE kind='bootstrap' AND id=?", (data["generation"],)
            ).fetchone():
                raise PermissionError("enrollment_bootstrap_consumed")
        return data

    def claim(self, generation):
        pending = self.pending()
        if generation != pending["generation"]:
            raise PermissionError("enrollment_binding_invalid")
        record = self._binding() | {
            "generation": generation,
            "enrollment_handle": secrets.token_hex(16),
            "created_at": int(self.clock()),
            "schema_version": 1,
        }
        with self.database() as db:
            try:
                db.execute("INSERT INTO x1_enrollment_consumed VALUES ('bootstrap',?)", (generation,))
            except sqlite3.IntegrityError:
                raise PermissionError("enrollment_bootstrap_consumed") from None
            # The completion event is the commit marker. A crash before it cannot yield a usable enrollment.
            self._write("ascend-x1-enrollment.dpapi", record)
            self._audit(db, generation, "ENROLLMENT_SUCCESS")
        self.repo.path("enrollment-bootstrap.json").unlink(missing_ok=True)
        self._secret("ascend-x1-enrollment-pending.dpapi").unlink(missing_ok=True)
        return record

    def load(self, handle=None):
        data = self._read("ascend-x1-enrollment.dpapi")
        generation = data.get("generation")
        if not isinstance(generation, str) or not HEX32.fullmatch(generation):
            raise PermissionError("enrollment_binding_invalid")
        try:
            binding = self._binding()
            if (
                set(data)
                != set(binding) | {"generation", "enrollment_handle", "created_at", "schema_version"}
                or any(data.get(key) != value for key, value in binding.items())
                or type(data.get("protocol")) is not int
                or type(data.get("schema_version")) is not int
                or data["schema_version"] != 1
                or type(data.get("created_at")) is not int
                or not HEX32.fullmatch(str(data.get("enrollment_handle", "")))
            ):
                raise PermissionError("enrollment_binding_invalid")
            if handle is not None and (
                not isinstance(handle, str) or not secrets.compare_digest(handle, data["enrollment_handle"])
            ):
                raise PermissionError("enrollment_handle_invalid")
        except Exception:
            self.audit(generation, "SECURITY_MISMATCH")
            self._invalidate_lease("SECURITY_MISMATCH")
            raise PermissionError("enrollment_binding_invalid") from None
        with self.database() as db:
            if self._revoked(db, generation):
                raise PermissionError("enrollment_revoked")
            if not db.execute(
                "SELECT 1 FROM x1_enrollment_events WHERE generation=? AND result_code='ENROLLMENT_SUCCESS'",
                (generation,),
            ).fetchone():
                raise PermissionError("enrollment_incomplete")
        return data

    def revoke(self, *, owner_authorized=False, security_mismatch=False):
        if owner_authorized is not True and security_mismatch is not True:
            raise PermissionError("owner_enrollment_required")
        data = self._read("ascend-x1-enrollment.dpapi")
        self.audit(data["generation"], "SECURITY_MISMATCH" if security_mismatch else "OWNER_REVOKED")
        self._invalidate_lease("SECURITY_MISMATCH" if security_mismatch else "READ_LEASE_REVOKED")
        return {"state": "PAIRING_STALE", "production_writes": False}

    def _invalidate_lease(self, code):
        from executors.ascend_extension.runtime import RuntimeAccess

        RuntimeAccess(self.repo, clock=self.clock).invalidate(code)

    def summary(self):
        try:
            self.load()
        except PermissionError as error:
            state = "NOT_ENROLLED" if error.args == ("not_enrolled",) else "PAIRING_STALE"
            return {"state": state, "enrolled": False}
        return {"state": "PAIRED", "enrolled": True}
