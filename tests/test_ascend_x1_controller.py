"""Offline X1 authority/receipt tests. Pairing cipher and all provider evidence are synthetic."""

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from executors.ascend_extension.controller import STEPS, ReadController, ledger, policy_gate, prepare
from executors.ascend_extension.native import canonical
from executors.ascend_extension.pairing import PairingRepository
from tests.test_ascend_native_host import authenticate, envelope

PICKUPS = ["1755", "1756", "1757", "1758", "1759", "1762", "1768", "1769"]
DELIVERIES = ["1761", "1766", "1767"]
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo(tmp_path):
    class Paths:
        def path(self, *parts):
            return tmp_path.joinpath(*parts)

    r = PairingRepository(Paths(), sid=lambda: "fixture", protect=lambda data, decrypt=False: data)
    r.capture("a" * 32)
    return r


def release(repo):
    return prepare(repo, "owner-x1-identity-1755-offline-fixture", "2026-09-11", PICKUPS, DELIVERIES)


def route(path="/loads"):
    return {
        "tab_id": 1,
        "document_id": "f" * 32,
        "eligible_tab_count": 1,
        "origin": "https://ascendtms.com",
        "path": path,
    }


def view_contract(view="ACTIVE_LOADS", selected=True):
    label = {
        "ACTIVE_LOADS": "Active Loads",
        "ALL_LOADS": "All Loads",
        "READY_FOR_ACCOUNTING": "Ready for Accounting",
        "OTHER": "OTHER",
    }[view]
    candidate = {
        "kind": "CONTROL",
        "label": label,
        "view": view,
        "visible": True,
        "aria_selected": True if selected else None,
        "aria_pressed": None,
        "aria_current": False,
        "active": False,
        "parent_active": False,
        "safe_classes": [],
        "parent_safe_classes": [],
        "data_view": None,
        "conflicting_identity": False,
        "visible_linked_panel": False,
        "unique_linked_panel": False,
    }
    return {
        "contract": "AscendLoadBoardViewContract",
        "version": 1,
        "provider": "AscendTMS",
        "source": "provider DOM",
        "candidate_control_count": 1,
        "candidate_count": 1,
        "candidate_bound_exceeded": False,
        "candidates": [candidate],
        "view": view if selected else "UNKNOWN",
        "confidence": "VERIFIED" if selected else "UNKNOWN",
        "reason": "PROVIDER_SIGNAL" if selected else "NO_PROVIDER_SIGNAL",
    }


def request(controller, *, path="/loads", operation=None):
    return {
        "kind": "READ_REQUEST",
        "route": route(path),
        "command": {
            "version": 1,
            "request_id": uuid4().hex,
            "operation": operation or STEPS[controller.index],
            "tenant_id": "booking-logistics",
            "actor": "FreightDesk/Avery",
            "load_id": "1755" if controller.index >= 2 else None,
            "expected_revision": controller.revision if controller.index >= 2 else None,
        },
    }


def result(dispatch, evidence, error=None):
    return {
        "kind": "READ_RESULT",
        "request_id": uuid4().hex,
        "command_request_id": dispatch["command"]["request_id"],
        "route": dispatch["route"],
        "evidence": evidence,
        "error_code": error,
    }


def session(auth=True):
    return {
        "authenticated_app": auth,
        "login_form_present": not auth,
        "nav_markers": ["Dashboard", "Loads", "Customers", "Carriers"] if auth else [],
    }


def board():
    rows = sorted(
        [
            {
                "load_id": n,
                "pick_date": "09/11/2026" if n in PICKUPS else "09/10/2026",
                "drop_date": "09/11/2026" if n in DELIVERIES else "09/12/2026",
            }
            for n in PICKUPS + DELIVERIES
        ],
        key=lambda r: int(r["load_id"]),
    )
    return {
        "view_contract": view_contract(),
        "source_view": "ACTIVE_LOADS",
        "coverage": "VISIBLE_BOARD_ONLY",
        "rows": rows,
        "board_hash": hashlib.sha256(canonical(rows)).hexdigest(),
    }


def ready(repo):
    release(repo)
    c = ReadController(repo)
    receipts = []
    for evidence in (session(), board()):
        receipts.append(c.finish(result(c.begin(request(c)), evidence)))
    receipts.append(
        c.finish(
            result(
                c.begin(request(c)),
                {
                    "load_id": "1755",
                    "exact_row": True,
                    "board_hash": c.revision,
                    "view_contract": view_contract(),
                },
            )
        )
    )
    return c, receipts


def identity(c, strategy="PROVIDER_DETAIL_FIELD"):
    return {
        "view_contract": view_contract(),
        "expected_load_id": "1755",
        "observed_load_id": "1755",
        "identity_strategy": strategy,
        "confidence": "VERIFIED",
        "board_hash": c.revision,
        "row_match": True,
        "opener_belongs_to_row": True,
        "unique_panel": True,
        "detail_field_match": strategy == "PROVIDER_DETAIL_FIELD",
        "direct_panel_reference": True,
        "opener_identity_match": strategy == "PROVIDER_OPENER_IDENTITY",
        "selection_transition": strategy == "PROVIDER_SELECTED_ROW_BINDING",
        "newly_visible": True,
    }


@pytest.mark.parametrize(
    "strategy", ["PROVIDER_DETAIL_FIELD", "PROVIDER_OPENER_IDENTITY", "PROVIDER_SELECTED_ROW_BINDING"]
)
def test_exact_sequence_receipts_and_no_operational_release(repo, strategy):
    c, receipts = ready(repo)
    assert receipts[0]["extension_pairing_verified"] is True
    assert receipts[0]["tenant_identity_source"] == "OWNER_ATTESTED"
    assert receipts[1]["pickup_count"] == 8 and receipts[1]["delivery_count"] == 3
    assert receipts[1]["coverage"] == "VISIBLE_BOARD_ONLY"
    assert receipts[2]["exact_row"] is True
    receipt = c.finish(result(c.begin(request(c)), identity(c, strategy)))
    assert receipt["identity_strategy"] == strategy and receipt["source"] == "live extension DOM"
    assert (
        receipt["state"] == "IDENTITY_VERIFIED_READS_BLOCKED" and receipt["operational_extraction"] is False
    )
    assert receipt["expected_load_id"] == receipt["observed_load_id"] == "1755"
    for op in ("ASCEND_READ_LOAD", "ASCEND_READ_STOPS", "ASCEND_READ_ASSIGNMENT", "ASCEND_SAVE_LOAD"):
        with pytest.raises(PermissionError):
            c.begin(request(c, operation=op))
    with ledger(repo) as db:
        events = [json.loads(row[0]) for row in db.execute("SELECT body FROM x1_read_events")]
    assert len(events) == 8
    assert all("timestamp" in event and event["production_writes"] is False for event in events)
    assert not any(
        value in json.dumps(events)
        for value in ("carrier", "driver", "PRIVATE", "cookie", "key", "nonce", "rows")
    )


def test_no_grant_and_single_prepare_restart_and_expiry(repo):
    c = ReadController(repo)
    with pytest.raises(PermissionError, match="READ_RELEASE_REQUIRED"):
        c.plan()
    grant = release(repo)
    assert c.plan()["load_id"] == "1755"
    expired = ReadController(repo, clock=lambda: grant["expires_at"] + 1)
    with pytest.raises(PermissionError, match="READ_TEST_EXPIRED"):
        expired.plan()
    with pytest.raises(PermissionError, match="READ_TEST_CONSUMED"):
        release(repo)
    c.begin(request(c))
    with pytest.raises(PermissionError, match="READ_TEST_CONSUMED"):
        ReadController(repo).plan()


@pytest.mark.parametrize("path,auth", [("/login.html", False), ("/", True), ("/loads", True)])
def test_login_and_dashboard_session_receipt(repo, path, auth):
    release(repo)
    c = ReadController(repo)
    receipt = c.finish(result(c.begin(request(c, path=path)), session(auth)))
    assert receipt["authenticated_app"] is auth
    assert receipt["state"] == ("READ_ONLY_READY" if auth else "STOPPED")
    if not auth:
        with pytest.raises(PermissionError):
            c.begin(request(c))


@pytest.mark.parametrize(
    "change", ["missing", "different_id", "date", "duplicate", "hash", "all_loads", "sensitive"]
)
def test_board_oracle_is_independent_date_classification(repo, change):
    release(repo)
    c = ReadController(repo)
    c.finish(result(c.begin(request(c)), session()))
    evidence = board()
    if change == "missing":
        evidence["rows"].pop()
    if change == "different_id":
        evidence["rows"][0]["load_id"] = "9999"
    if change == "date":
        evidence["rows"][0]["pick_date"] = "09/12/2026"
    if change == "duplicate":
        evidence["rows"][1] = evidence["rows"][0]
    if change == "hash":
        evidence["board_hash"] = "a" * 64
    if change == "all_loads":
        evidence["source_view"] = "ALL_LOADS"
    if change == "sensitive":
        evidence["rows"][0]["private_notes"] = "PRIVATE_SECRET"
    if change != "hash":
        evidence["board_hash"] = hashlib.sha256(canonical(evidence["rows"])).hexdigest()
    with pytest.raises((PermissionError, ValueError)):
        c.finish(result(c.begin(request(c)), evidence))


@pytest.mark.parametrize("extra_due", [False, True])
def test_non_service_date_rows_do_not_expand_operational_manifest(repo, extra_due):
    release(repo)
    c = ReadController(repo)
    c.finish(result(c.begin(request(c)), session()))
    evidence = board()
    evidence["rows"].append(
        {
            "load_id": "9999",
            "pick_date": "09/11/2026" if extra_due else "09/20/2026",
            "drop_date": "09/21/2026",
        }
    )
    evidence["board_hash"] = hashlib.sha256(canonical(evidence["rows"])).hexdigest()
    dispatch = c.begin(request(c))
    if extra_due:
        with pytest.raises(PermissionError, match="BOARD_MISMATCH"):
            c.finish(result(dispatch, evidence))
    else:
        receipt = c.finish(result(dispatch, evidence))
        assert receipt["observed_row_count"] == 12
        assert receipt["service_date_row_count"] == 11
        assert receipt["pickup_count"] == 8 and receipt["delivery_count"] == 3
        assert "9999" not in json.dumps(receipt)


@pytest.mark.parametrize(
    "change", ["wrong_id", "no_proof", "wrong_hash", "click_only", "raw", "coerced_true", "unknown_strategy"]
)
def test_identity_conflict_or_missing_is_never_receipt(repo, change):
    c, _ = ready(repo)
    e = identity(c)
    if change == "wrong_id":
        e["observed_load_id"] = "1756"
    if change == "no_proof":
        e["detail_field_match"] = False
    if change == "wrong_hash":
        e["board_hash"] = "b" * 64
    if change == "click_only":
        e.update(identity_strategy="PROVIDER_SELECTED_ROW_BINDING", selection_transition=False)
    if change == "raw":
        e["notes"] = "PRIVATE_SECRET"
    if change == "coerced_true":
        e["row_match"] = 1
    if change == "unknown_strategy":
        e["identity_strategy"] = "FREIGHTDESK_CLICKED"
    with pytest.raises((PermissionError, ValueError)):
        c.finish(result(c.begin(request(c)), e))


@pytest.mark.parametrize(
    "change",
    [
        {"operation": "execute_js"},
        {"operation": "eval"},
        {"operation": "shell"},
        {"operation": "run_script"},
        {"operation": "ASCEND_SAVE_LOAD"},
        {"selector": "PRIVATE"},
        {"url": "https://ascendtms.com/loads"},
        {"script": "PRIVATE"},
        {"tenant_id": "other"},
        {"actor": "other"},
        {"operation": "ASCEND_READ_LOAD", "load_id": "1755", "expected_revision": "a" * 64},
    ],
)
def test_commands_rejected_before_dispatch(repo, change):
    release(repo)
    c = ReadController(repo)
    r = request(c)
    r["command"].update(change)
    with pytest.raises((ValueError, PermissionError)):
        c.begin(r)
    assert c.pending is None


def test_navigation_pause_timeout_duplicate_and_unknown_error(repo):
    c, _ = ready(repo)
    r = request(c)
    r["route"]["document_id"] = "e" * 32
    with pytest.raises(PermissionError, match="TAB_STATE_CHANGED"):
        c.begin(r)
    c.gate = lambda repo: (_ for _ in ()).throw(PermissionError("READ_POLICY_BLOCKED"))
    with pytest.raises(PermissionError, match="READ_POLICY_BLOCKED"):
        c.begin(request(c))
    c.gate = policy_gate
    dispatch = c.begin(request(c))
    c.clock = lambda: c.deadline + 1
    with pytest.raises(PermissionError, match="READ_TIMEOUT"):
        c.finish(result(dispatch, identity(c)))
    receipt = c.fail(Exception("PRIVATE_SECRET_DRIVER_TOKEN"))
    assert receipt["error_code"] == "READ_EXECUTION_FAILED" and "PRIVATE" not in json.dumps(receipt)


def test_pairing_bound_host_dispatch_and_duplicate(repo):
    release(repo)
    host, package, _ = authenticate(repo)
    seq = 0

    def send(body):
        nonlocal seq
        seq += 1
        return host.handle(envelope(host, package, body, seq))["envelope"]["body"]

    plan = send({"kind": "READ_PLAN", "request_id": uuid4().hex})
    assert plan["kind"] == "READ_PLAN" and not plan["read_dispatch_enabled"]
    req = request(host.reads)
    dispatch = send(req)
    assert dispatch["kind"] == "READ_DISPATCH"
    receipt = send(result(dispatch, session()))
    assert receipt["receipt"]["authenticated_app"] is True
    # Reusing a consumed request in the correct next operation remains rejected durably.
    req["command"]["operation"] = "ASCEND_GET_ACTIVE_LOADS"
    duplicate = send(req)
    assert duplicate["receipt"]["error_code"] == "DUPLICATE_REQUEST"
    repo.reset()
    with pytest.raises(FileNotFoundError):
        send({"kind": "READ_PLAN", "request_id": uuid4().hex})


def test_policy_controls_are_read_only_and_fail_closed(repo):
    path = repo.paths.path("Data", "booking-logistics", "ascend.sqlite3")
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE records(tenant TEXT,kind TEXT,body TEXT)")
        db.execute(
            "INSERT INTO records VALUES (?,?,?)", ("booking-logistics", "ascend_controls", '{"paused":true}')
        )
    with pytest.raises(PermissionError, match="READ_POLICY_BLOCKED"):
        release(repo)


def test_node_routing_and_signed_controller_fixtures():
    result = subprocess.run(
        ["node", str(ROOT / "scripts" / "check-ascend-x1-controller.js")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
