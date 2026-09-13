"""Identified X1 source/native release; never creates read authority or changes enrollment."""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.core.runtime import RuntimePaths
from executors.ascend_extension.bridge_build import BUILD
from executors.ascend_extension.enrollment import PINNED_EXTENSION_ID
from executors.ascend_extension.pairing import HOST_NAME, PairingRepository
from scripts.ascend_native_selftest import probe

ROOT = Path(__file__).resolve().parents[1]
RELEASE = "x1-0.6.3-20260913"
SAFE_ERRORS = frozenset({
    "RELEASE_READ_PENDING", "RELEASE_AUTHORITY_ACTIVE", "RELEASE_JOB_ACTIVE", "RELEASE_FILE_CHANGED",
    "RELEASE_PENDING_FILE_EXISTS", "RELEASE_SOURCE_INVALID", "RELEASE_INSTALLATION_MISMATCH",
    "RELEASE_SOURCE_UNCOMMITTED", "RELEASE_MANIFEST_INVALID", "RELEASE_BACKUP_MISMATCH",
    "RELEASE_COMPILE_FAILED", "RELEASE_SOURCE_CHANGED", "RELEASE_OWNER_REQUIRED",
    "RELEASE_SELFTEST_ALREADY_ATTEMPTED", "RELEASE_SELFTEST_REQUIRED", "RELEASE_RECEIPT_EXISTS",
    "RELEASE_INSTALL_RECEIPT_FAILED",
})


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_runtime(path: Path) -> Path:
    paths = RuntimePaths.from_environment()
    relative = Path(path).absolute().relative_to(paths.root.absolute())
    return paths.path(*relative.parts)


def require_idle(repo: PairingRepository, *, now: float | None = None) -> None:
    """Observe only; do not cancel, expire, reconcile or mutate existing authority."""
    now = time.time() if now is None else now
    runtime = repo.path("runtime.sqlite3")
    if runtime.exists():
        with sqlite3.connect(runtime.as_uri() + "?mode=ro", uri=True, timeout=3) as db:
            item = db.execute("SELECT body FROM runtime_state WHERE id=1").fetchone()
            state = json.loads(item[0]) if item else {}
            item = db.execute("SELECT body FROM runtime_leases ORDER BY rowid DESC LIMIT 1").fetchone()
            lease = json.loads(item[0]) if item else None
            if state.get("pending") is not None or state.get("mapping_capture_requested"):
                raise ValueError("RELEASE_READ_PENDING")
            if lease and now < lease["expires_at"] and state.get("revoked_generation") != lease["generation"]:
                raise ValueError("RELEASE_AUTHORITY_ACTIVE")
    coordinator = repo.path("mapping-orchestrator.sqlite3")
    if coordinator.exists():
        with sqlite3.connect(coordinator.as_uri() + "?mode=ro", uri=True, timeout=3) as db:
            for row in db.execute("SELECT body FROM jobs"):
                job = json.loads(row[0])
                if job["stage"] not in {"COMPLETE", "STOPPED"} and not (
                    job["stage"] == "OWNER_REVIEW_REQUIRED" and job.get("cleanup_complete") is True
                ):
                    raise ValueError("RELEASE_JOB_ACTIVE")


def atomic_replace(candidate: Path, target: Path, *, expected_before: str, expected_after: str,
                   replace: Callable = os.replace) -> None:
    """One verified local file, same-directory atomic replacement; no directory moves."""
    candidate, target = checked_runtime(candidate), checked_runtime(target)
    if digest(target) != expected_before or digest(candidate) != expected_after:
        raise ValueError("RELEASE_FILE_CHANGED")
    pending = checked_runtime(target.with_name(target.name + ".pending"))
    if pending.exists():
        raise ValueError("RELEASE_PENDING_FILE_EXISTS")
    owns_pending = False
    try:
        with pending.open("xb") as output:
            owns_pending = True
            output.write(candidate.read_bytes())
            output.flush()
            os.fsync(output.fileno())
        if digest(pending) != expected_after or digest(target) != expected_before:
            raise ValueError("RELEASE_FILE_CHANGED")
        replace(pending, target)
        if digest(target) != expected_after:
            raise ValueError("RELEASE_FILE_CHANGED")
    finally:
        if owns_pending and pending.exists():
            checked_runtime(pending).unlink()


def source_hashes() -> dict[str, str]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    names = result.stdout.decode().split("\0")
    selected = [name for name in names if name and (
        name in {"requirements.lock", "pyproject.toml"} or
        name.startswith(("app/", "executors/", "integrations/", "extensions/ascend-x1/", "scripts/"))
        and Path(name).suffix in {".py", ".js", ".json", ".html", ".css", ".ps1", ".cs"}
    )]
    values = {}
    for name in sorted(selected):
        path = ROOT / name
        if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("RELEASE_SOURCE_INVALID")
        values[name] = digest(path)
    return values


def release_root(repo: PairingRepository) -> Path:
    return repo.paths.path("Data", "Development", "X1Releases", RELEASE)


def configuration(repo: PairingRepository) -> str:
    config = repo.config()
    manifest = json.loads(repo.path("host-manifest.json").read_text(encoding="utf-8"))
    if (config["extension_id"] != PINNED_EXTENSION_ID or
        manifest.get("name") != HOST_NAME or manifest.get("type") != "stdio" or
        manifest["allowed_origins"] != [f"chrome-extension://{PINNED_EXTENSION_ID}/"] or
        manifest["path"] != str(repo.path("FreightDeskAscendHost.exe"))):
        raise ValueError("RELEASE_INSTALLATION_MISMATCH")
    return f"chrome-extension://{PINNED_EXTENSION_ID}/"


def prepare(repo: PairingRepository) -> dict[str, Any]:
    """Compile and hash only. Candidate execution is a separate, recorded boundary."""
    require_idle(repo)
    configuration(repo)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, check=True)
    if status.stdout.strip():
        raise ValueError("RELEASE_SOURCE_UNCOMMITTED")
    manifest = json.loads((ROOT / "extensions/ascend-x1/manifest.json").read_text())
    if (manifest["version"] != BUILD["extension_version"] or
        manifest["host_permissions"] != ["https://ascendtms.com/*"] or
        set(manifest["permissions"]) != {"nativeMessaging", "storage", "alarms", "scripting"} or
        "webbridge-v2" in json.dumps(manifest)):
        raise ValueError("RELEASE_MANIFEST_INVALID")
    base = release_root(repo)
    backup = checked_runtime(base / "pre-update/FreightDeskAscendHost.exe")
    if digest(backup) != digest(repo.path("FreightDeskAscendHost.exe")):
        raise ValueError("RELEASE_BACKUP_MISMATCH")
    folder = checked_runtime(base / "candidate")
    folder.mkdir(parents=True, exist_ok=False)
    code = (ROOT / "scripts/native_host_launcher.cs").read_text(encoding="utf-8")
    code = code.replace("__PYTHON__", str(ROOT / ".tools/python/python.exe").replace('"', '""'))
    code = code.replace("__SOURCE__", str(ROOT).replace('"', '""'))
    source, binary = folder / "launcher.cs", folder / "FreightDeskAscendHost.exe"
    source.write_text(code, encoding="utf-8")
    compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    built = subprocess.run([str(compiler), "/nologo", "/target:exe", "/out:" + str(binary), str(source)],
                           capture_output=True, timeout=30)
    if built.returncode:
        raise ValueError("RELEASE_COMPILE_FAILED")
    value = {"release": RELEASE, "build": BUILD, "source_hashes": source_hashes(),
             "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                             check=True, text=True).stdout.strip(),
             "python_sha256": digest(ROOT / ".tools/python/python.exe"),
             "candidate_host_sha256": digest(binary), "prior_host_sha256": digest(backup),
             "prior_launcher_sha256": digest(checked_runtime(base / "pre-update/launcher.cs")),
             "candidate_launcher_sha256": digest(source), "candidate_execution": "NOT_RUN",
             "v2_enabled": False, "production_writes": False}
    checked_runtime(base / "prepared.json").write_text(json.dumps(value, sort_keys=True, indent=2))
    return {"status": "RELEASE_STAGED", "release": RELEASE, "build": BUILD,
            "candidate_execution": "NOT_RUN", "source_file_count": len(value["source_hashes"]),
            "installed_host_changed": False, "production_writes": False}


def verify(repo: PairingRepository) -> dict[str, Any]:
    configuration(repo)
    base = release_root(repo)
    value = json.loads(checked_runtime(base / "prepared.json").read_text())
    if (value["release"] != RELEASE or value["build"] != BUILD or value["v2_enabled"] is not False or
        value["production_writes"] is not False or value["source_hashes"] != source_hashes() or
        value["python_sha256"] != digest(ROOT / ".tools/python/python.exe") or
        value["candidate_host_sha256"] != digest(checked_runtime(base / "candidate/FreightDeskAscendHost.exe")) or
        value["candidate_launcher_sha256"] != digest(checked_runtime(base / "candidate/launcher.cs")) or
        value["prior_launcher_sha256"] != digest(checked_runtime(base / "pre-update/launcher.cs")) or
        value["prior_host_sha256"] != digest(checked_runtime(base / "pre-update/FreightDeskAscendHost.exe"))):
        raise ValueError("RELEASE_SOURCE_CHANGED")
    return value


def check_candidate(repo: PairingRepository, *, owner_authorized: bool = False) -> dict[str, Any]:
    """One synthetic process check; denial/uncertainty stays recorded and cannot auto-retry."""
    if owner_authorized is not True:
        raise PermissionError("RELEASE_OWNER_REQUIRED")
    require_idle(repo)
    value = verify(repo)
    base = release_root(repo)
    receipt = checked_runtime(base / "candidate-selftest.json")
    if receipt.exists():
        raise ValueError("RELEASE_SELFTEST_ALREADY_ATTEMPTED")
    result = {"release": RELEASE, "candidate_host_sha256": value["candidate_host_sha256"],
              "status": "STARTED", "safe_error_code": "RELEASE_SELFTEST_INCOMPLETE",
              "production_reads": False, "production_writes": False}
    # Reserve before dispatch. Process exit/crash leaves a consumed, incomplete receipt.
    with receipt.open("x", encoding="utf-8") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.flush()
        os.fsync(output.fileno())
    result.update(probe(str(checked_runtime(base / "candidate/FreightDeskAscendHost.exe")), configuration(repo)))
    receipt.write_text(json.dumps(result, sort_keys=True, indent=2), encoding="utf-8")
    return result


def install_host(repo: PairingRepository, *, rollback: bool = False,
                 owner_authorized: bool = False) -> dict[str, Any]:
    if owner_authorized is not True:
        raise PermissionError("RELEASE_OWNER_REQUIRED")
    require_idle(repo)
    value = verify(repo)
    base = release_root(repo)
    if not rollback:
        test_path = checked_runtime(base / "candidate-selftest.json")
        test = json.loads(test_path.read_text()) if test_path.exists() else {}
        if (test.get("release") != RELEASE or test.get("status") != "PASS" or
            test.get("safe_error_code") != "SELF_TEST_OK" or
            test.get("candidate_host_sha256") != value["candidate_host_sha256"] or
            test.get("production_reads") is not False or test.get("production_writes") is not False):
            raise ValueError("RELEASE_SELFTEST_REQUIRED")
    before, after = value["prior_host_sha256"], value["candidate_host_sha256"]
    candidate = checked_runtime(base / "candidate/FreightDeskAscendHost.exe")
    if rollback:
        before, after = after, before
        candidate = checked_runtime(base / "pre-update/FreightDeskAscendHost.exe")
    receipt = checked_runtime(base / ("rollback.json" if rollback else "installed.json"))
    if receipt.exists():
        raise ValueError("RELEASE_RECEIPT_EXISTS")
    cs_before, cs_after = value["prior_launcher_sha256"], value["candidate_launcher_sha256"]
    cs_candidate = checked_runtime(base / "candidate/launcher.cs")
    cs_recovery = checked_runtime(base / "pre-update/launcher.cs")
    if rollback:
        cs_before, cs_after = cs_after, cs_before
        cs_candidate, cs_recovery = cs_recovery, cs_candidate
    # Source metadata changes first; a locked executable leaves its original version in place.
    # Recover only our source replacement, never overwrite an unexpected external change.
    atomic_replace(cs_candidate, repo.path("launcher.cs"), expected_before=cs_before, expected_after=cs_after)
    try:
        require_idle(repo)
        atomic_replace(candidate, repo.path("FreightDeskAscendHost.exe"), expected_before=before, expected_after=after)
    except Exception:
        atomic_replace(cs_recovery, repo.path("launcher.cs"), expected_before=cs_after, expected_after=cs_before)
        raise
    result = {"status": "HOST_ROLLED_BACK" if rollback else "HOST_INSTALLED", "release": RELEASE,
              "installed_host_sha256": after, "extension_reload_required": True,
              "enrollment_changed": False, "authority_changed": False, "production_writes": False}
    try:
        with receipt.open("x", encoding="utf-8") as output:
            json.dump(result, output, sort_keys=True, indent=2)
            output.flush()
            os.fsync(output.fileno())
    except OSError:
        raise ValueError("RELEASE_INSTALL_RECEIPT_FAILED") from None
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "verify", "check-candidate", "install-host", "rollback-host"])
    parser.add_argument("--owner-authorized", action="store_true")
    args = parser.parse_args()
    repo = PairingRepository()
    try:
        if args.action == "prepare":
            result = prepare(repo)
        elif args.action == "verify":
            value = verify(repo)
            result = {"status": "RELEASE_ARTIFACTS_VERIFIED", "release": RELEASE, "build": value["build"],
                      "source_file_count": len(value["source_hashes"]), "production_writes": False}
        elif args.action == "check-candidate":
            result = check_candidate(repo, owner_authorized=args.owner_authorized)
        else:
            result = install_host(repo, rollback=args.action == "rollback-host", owner_authorized=args.owner_authorized)
        print(json.dumps(result, sort_keys=True))
        if result.get("status") == "STOPPED":
            raise SystemExit(1)
    except Exception as error:
        code = str(error) if isinstance(error, (ValueError, PermissionError)) and str(error) in SAFE_ERRORS else "RELEASE_FAILED"
        print(json.dumps({"status": "STOPPED", "error_code": code,
                          "installation_requires_hash_inspection": code == "RELEASE_INSTALL_RECEIPT_FAILED",
                          "production_writes": False}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
