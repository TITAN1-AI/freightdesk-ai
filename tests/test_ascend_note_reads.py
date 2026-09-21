"""Ascend private/public note read-back. ALLOW capture, not LIVE_VALIDATED."""

import subprocess
from datetime import timedelta
from pathlib import Path

from app.models.domain import ActionPolicy, utcnow
from tests.test_agent_sessions import mint_agent
from tests.test_ascend_notes import mint_approval
from tests.test_portable_leases import portable_headers, sign_in, snapshot


def agent_headers(token):
    return {"Authorization": f"Bearer {token}"}


def fixture_reader(private_note="ops private", public_note="ops public"):
    def execute(job):
        assert job["load_id"]
        return {
            "verified": True,
            "private_note": private_note,
            "public_note": public_note,
            "private_note_present": True,
            "public_note_present": True,
            "opener_strategy": "already_open",
            "verify_reason": "verified_via_note_controls",
            "bridge_version": "0.1.13",
            "tab_hint": "scratch:9",
        }
    return execute


def test_note_read_policy_is_allow(plane):
    assert plane.policy("ASCEND_READ_LOAD_NOTES") == ActionPolicy.ALLOW
    assert plane.policy("ASCEND_ADD_INTERNAL_NOTE") == ActionPolicy.APPROVAL_REQUIRED


def test_note_read_empty_capture_is_safe(client):
    missing = client.get("/v1/ascend/loads/1763/notes")
    assert missing.status_code == 200
    body = missing.json()
    assert body["load_id"] == "1763"
    assert body["found"] is False
    assert body["private_note"] is None
    assert body["public_note"] is None
    assert body["live_validated"] is False
    assert body["production_writes"] is False
    assert body["silent_save_forbidden"] is True
    assert body["atlas_private"] == "textarea#scratch"
    assert body["atlas_public"] == "#notes"


def test_note_capture_dispatches_without_approval(client):
    token = mint_agent(client)
    posted = client.post("/v1/ascend/loads/1763/notes/capture", headers=agent_headers(token))
    assert posted.status_code == 200
    body = posted.json()
    assert body["status"] == "DISPATCHED"
    assert body["action"] == "ASCEND_READ_LOAD_NOTES"
    assert body["policy"] == "ALLOW"
    assert body["commit_kind"] == "READ_ONLY"
    assert body["save_variant"] == "NONE"
    assert body["allow_whole_form_save"] is False
    assert body["silent_save_forbidden"] is True
    assert body["live_validated"] is False
    assert body["verified"] is False
    claimed = client.get("/v1/portable/writes/pending", headers=agent_headers(token)).json()
    assert claimed["pending"] is True
    assert claimed["action"] == "READ_LOAD_NOTES"
    assert claimed["write_id"] == body["write_id"]
    assert "text" not in claimed
    completed = client.post(
        f"/v1/portable/writes/{body['write_id']}/complete",
        json={
            "verified": True,
            "note_present": True,
            "private_note_present": True,
            "public_note_present": True,
            "private_note": "internal desk note",
            "public_note": "visible to customer",
            "error_code": None,
            "live_validated": False,
            "production_writes": False,
            "stage": "verify",
            "opener_strategy": "already_open",
            "commit_kind": "READ_ONLY",
            "save_variant": "NONE",
            "tab_hint": "scratch:9",
            "verify_reason": "verified_via_note_controls",
            "bridge_version": "0.1.13",
        },
        headers=agent_headers(token),
    )
    assert completed.status_code == 200
    receipt = completed.json()
    assert receipt["status"] == "VERIFIED"
    assert receipt["verified"] is True
    assert receipt["private_note"] == "internal desk note"
    assert receipt["public_note"] == "visible to customer"
    assert receipt["tab_hint"] == "scratch:9"
    assert receipt["bridge_version"] == "0.1.13"
    assert receipt["verify_reason"] == "verified_via_note_controls"
    latest = client.get("/v1/ascend/loads/1763/notes", headers=agent_headers(token)).json()
    assert latest["found"] is True
    assert latest["private_note"] == "internal desk note"
    assert latest["public_note"] == "visible to customer"
    assert latest["capture_id"] == body["write_id"]
    merged = client.get("/v1/ascend/loads/1763", headers=agent_headers(token)).json()
    assert merged["notes"]["found"] is True
    assert merged["notes"]["private_note"] == "internal desk note"


def test_note_capture_fixture_executor_verifies(client):
    token = mint_agent(client)
    client.app.state.note_reads.executor = fixture_reader()
    posted = client.post("/v1/ascend/loads/1777/notes/capture", headers=agent_headers(token))
    assert posted.status_code == 200
    body = posted.json()
    assert body["status"] == "VERIFIED"
    assert body["private_note"] == "ops private"
    assert body["public_note"] == "ops public"
    assert body["bridge_version"] == "0.1.13"
    empty_scratch = fixture_reader(private_note="", public_note="board note")
    client.app.state.note_reads.executor = empty_scratch
    second = client.post("/v1/ascend/loads/1777/notes/capture", headers=agent_headers(token)).json()
    assert second["status"] == "VERIFIED"
    assert second["private_note"] == ""
    assert second["public_note"] == "board note"


def test_note_capture_empty_scratch_with_control_is_verified(client):
    token = mint_agent(client)
    posted = client.post("/v1/ascend/loads/1763/notes/capture", headers=agent_headers(token)).json()
    client.get("/v1/portable/writes/pending", headers=agent_headers(token))
    completed = client.post(
        f"/v1/portable/writes/{posted['write_id']}/complete",
        json={
            "verified": True,
            "note_present": True,
            "private_note_present": True,
            "public_note_present": False,
            "private_note": "",
            "public_note": None,
            "error_code": None,
            "live_validated": False,
            "production_writes": False,
            "commit_kind": "READ_ONLY",
            "save_variant": "NONE",
            "tab_hint": "scratch:9",
            "verify_reason": "verified_via_scratch_scan",
            "bridge_version": "0.1.13",
        },
        headers=agent_headers(token),
    )
    assert completed.status_code == 200
    receipt = completed.json()
    assert receipt["status"] == "VERIFIED"
    assert receipt["private_note"] == ""
    assert receipt["public_note"] is None
    assert receipt["private_note_present"] is True
    latest = client.get("/v1/ascend/loads/1763/notes", headers=agent_headers(token)).json()
    assert latest["found"] is True
    assert latest["private_note"] == ""
    assert latest["tab_hint"] == "scratch:9"


def test_note_capture_complete_rejects_live_flags(client):
    token = mint_agent(client)
    posted = client.post("/v1/ascend/loads/1763/notes/capture", headers=agent_headers(token)).json()
    client.get("/v1/portable/writes/pending", headers=agent_headers(token))
    denied = client.post(
        f"/v1/portable/writes/{posted['write_id']}/complete",
        json={"verified": True, "note_present": True, "private_note_present": True,
              "private_note": "x", "live_validated": True, "production_writes": False},
        headers=agent_headers(token),
    )
    assert denied.status_code == 409


def test_note_capture_times_out_unclaimed(client):
    token = mint_agent(client)
    posted = client.post("/v1/ascend/loads/1763/notes/capture", headers=agent_headers(token)).json()
    store = client.app.state.control.store
    record = store.get("booking-logistics", "ascend_note_capture", posted["write_id"])
    stale = (utcnow() - timedelta(seconds=120)).isoformat()
    record["created_at"] = stale
    record["dispatched_at"] = stale
    record["claim_deadline_at"] = stale
    store.put("booking-logistics", "ascend_note_capture", posted["write_id"], record)
    fetched = client.get(f"/v1/ascend/writes/{posted['write_id']}", headers=agent_headers(token))
    assert fetched.json()["status"] == "FAILED"
    assert fetched.json()["error_code"] == "BRIDGE_CLAIM_TIMEOUT"


def test_note_capture_shares_claim_queue_with_writes(client):
    token = mint_agent(client)
    minted = mint_approval(client, token, "1763")
    note = client.post("/v1/ascend/loads/1763/notes",
                       json={"text": "first note", "approval_token": minted["approval_token"]},
                       headers=agent_headers(token)).json()
    capture = client.post("/v1/ascend/loads/1763/notes/capture", headers=agent_headers(token)).json()
    first = client.get("/v1/portable/writes/pending", headers=agent_headers(token)).json()
    assert first["write_id"] == note["write_id"]
    assert first["action"] == "ADD_INTERNAL_NOTE"
    client.post(f"/v1/portable/writes/{note['write_id']}/complete",
                json={"verified": False, "note_present": False,
                      "error_code": "NOTE_COMMIT_REQUIRES_OWNER_PATH",
                      "live_validated": False, "production_writes": False},
                headers=agent_headers(token))
    second = client.get("/v1/portable/writes/pending", headers=agent_headers(token)).json()
    assert second["write_id"] == capture["write_id"]
    assert second["action"] == "READ_LOAD_NOTES"


def test_note_capture_requires_session(client):
    client.headers.pop("Authorization", None)
    assert client.get("/v1/ascend/loads/1763/notes").status_code == 401
    assert client.post("/v1/ascend/loads/1763/notes/capture").status_code == 401


def test_note_capture_dashboard_asset_is_served(client):
    assert client.get("/assets/portable-note-reads.js").status_code == 200
    html = client.get("/").text
    assert "portable-note-reads.js" in html
    assert "Queue note read-back" in html
    checked = subprocess.run(
        ["node", "--check", str(Path("app/dashboard/portable-note-reads.js"))],
        capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr or checked.stdout


def test_harvest_ops_fields_surface_on_load_by_id(client):
    token = sign_in(client)
    lease = client.post("/v1/portable/leases", json={"origin": "https://ascendtms.com"},
                        headers=portable_headers(token=token)).json()
    payload = snapshot(lease["id"], rows=[{
        "load_id": "1763",
        "pick_date": "09/15/2026",
        "drop_date": "09/16/2026",
        "load_status": "Dispatched",
        "last_contact_tracking": "GPS 12 min",
        "customer": "Acme Freight",
        "public_notes": "dock 4",
        "carrier": "Example Carrier",
        "picks": "Dallas, TX",
        "drops": "Houston, TX",
    }])
    accepted = client.post("/v1/portable/harvest", json=payload,
                           headers=portable_headers(token=lease["lease_token"]))
    assert accepted.status_code == 200
    found = client.get("/v1/ascend/loads/1763").json()
    assert found["found"] is True
    assert found["fields"]["last_contact_tracking"]["value"] == "GPS 12 min"
    assert found["fields"]["customer"]["value"] == "Acme Freight"
    assert found["fields"]["public_notes"]["value"] == "dock 4"
    assert found["fields"]["carrier"]["value"] == "Example Carrier"
    assert found["fields"]["picks"]["value"] == "Dallas, TX"
    assert "income" not in found["fields"]
    board = client.get("/v1/ascend/loads").json()
    assert board["loads"][0]["fields"]["last_contact_tracking"]["value"] == "GPS 12 min"
