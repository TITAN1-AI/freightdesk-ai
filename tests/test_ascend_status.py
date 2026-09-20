"""Ascend load-status write facade. Not LIVE_VALIDATED."""

from datetime import timedelta

from app.models.domain import ActionPolicy, utcnow
from tests.test_agent_sessions import mint_agent
from tests.test_ascend_notes import agent_headers, mint_approval as mint_note_approval
from tests.test_portable_leases import sign_in


def mint_status_approval(client, token, load_id="1763", status=None, allow_whole_form_save=False,
                         action="ASCEND_CHANGE_LOAD_STATUS"):
    body = {"action": action, "load_id": load_id, "allow_whole_form_save": allow_whole_form_save}
    if status is not None:
        body["status"] = status
    response = client.post("/v1/ascend/approvals", json=body, headers=agent_headers(token))
    assert response.status_code == 200
    minted = response.json()
    assert minted["action"] == "ASCEND_CHANGE_LOAD_STATUS"
    assert minted["one_use"] is True
    assert minted["live_validated"] is False
    assert minted["production_writes"] is False
    assert minted["approval_token"]
    assert "UNKNOWN" not in minted["allowed_statuses"]
    return minted


def fixture_executor():
    ledger = {}

    def execute(job):
        ledger[job["load_id"]] = job["status"]
        return {
            "verified": True,
            "status_matched": True,
            "observed_status": job["status"],
            "error_code": None,
            "commit_kind": "WHOLE_FORM_SAVE" if job.get("allow_whole_form_save") else None,
            "save_variant": "SAVE_STAY" if job.get("allow_whole_form_save") else None,
            "stage": "verify",
        }

    return execute, ledger


def test_status_policy_default_is_approval_required(plane):
    assert plane.policy("ASCEND_CHANGE_LOAD_STATUS") == ActionPolicy.APPROVAL_REQUIRED
    assert plane.policy("ASCEND_ADD_INTERNAL_NOTE") == ActionPolicy.APPROVAL_REQUIRED


def test_status_write_rejected_without_approval(client):
    token = mint_agent(client)
    response = client.post("/v1/ascend/loads/1763/status", json={"status": "Dispatched"},
                           headers=agent_headers(token))
    assert response.status_code == 403
    receipt = response.json()
    assert receipt["status"] == "PENDING_APPROVAL"
    assert receipt["action"] == "ASCEND_CHANGE_LOAD_STATUS"
    assert receipt["requested_status"] == "Dispatched"
    assert receipt["evidence_class"] == "CANDIDATE"
    assert receipt["live_validated"] is False
    assert receipt["production_writes"] is False
    assert receipt["verified"] is False
    assert receipt["silent_save_forbidden"] is True
    assert receipt["error_code"] == "approval_required"


def test_status_write_rejects_unknown_and_invalid(client):
    token = mint_agent(client)
    unknown = client.post("/v1/ascend/loads/1763/status", json={"status": "UNKNOWN"},
                          headers=agent_headers(token))
    assert unknown.status_code == 409
    invented = client.post("/v1/ascend/loads/1763/status", json={"status": "Yeeted"},
                           headers=agent_headers(token))
    assert invented.status_code == 409


def test_status_write_accepts_to_be_billed(client):
    token = mint_agent(client)
    minted = mint_status_approval(client, token, "1763", status="To Be Billed")
    assert "To Be Billed" in minted["allowed_statuses"]
    assert "Driver Assigned" in minted["allowed_statuses"]
    assert "UNKNOWN" not in minted["allowed_statuses"]
    posted = client.post("/v1/ascend/loads/1763/status",
                         json={"status": "To Be Billed", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token))
    assert posted.status_code == 200
    receipt = posted.json()
    assert receipt["status"] == "DISPATCHED"
    assert receipt["requested_status"] == "To Be Billed"
    assert "To Be Billed" in receipt["allowed_statuses"]


def test_status_write_happy_path_mocked_verify_after_write(client):
    token = mint_agent(client)
    execute, ledger = fixture_executor()
    client.app.state.status.executor = execute
    minted = mint_status_approval(client, token, "1763", status="Dispatched",
                                  allow_whole_form_save=True)
    response = client.post("/v1/ascend/loads/1763/status",
                           json={"status": "Dispatched", "approval_token": minted["approval_token"]},
                           headers=agent_headers(token))
    assert response.status_code == 200
    receipt = response.json()
    assert receipt["status"] == "VERIFIED"
    assert receipt["verified"] is True
    assert receipt["status_matched"] is True
    assert receipt["requested_status"] == "Dispatched"
    assert receipt["observed_status"] == "Dispatched"
    assert receipt["live_validated"] is False
    assert receipt["error_code"] is None
    assert ledger["1763"] == "Dispatched"
    fetched = client.get(f"/v1/ascend/writes/{receipt['write_id']}", headers=agent_headers(token))
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "VERIFIED"
    assert fetched.json()["tab_hint"] is None or fetched.json()["bridge_version"] is None


def test_status_approval_is_one_use_and_status_bound(client):
    token = mint_agent(client)
    client.app.state.status.executor = fixture_executor()[0]
    minted = mint_status_approval(client, token, "1763", status="Dispatched")
    wrong_load = client.post("/v1/ascend/loads/1755/status",
                             json={"status": "Dispatched", "approval_token": minted["approval_token"]},
                             headers=agent_headers(token))
    assert wrong_load.status_code == 403
    assert wrong_load.json()["error_code"] == "approval_binding_invalid"
    wrong_status = client.post("/v1/ascend/loads/1763/status",
                               json={"status": "Delivered", "approval_token": minted["approval_token"]},
                               headers=agent_headers(token))
    assert wrong_status.status_code == 403
    assert wrong_status.json()["error_code"] == "approval_status_mismatch"
    first = client.post("/v1/ascend/loads/1763/status",
                        json={"status": "Dispatched", "approval_token": minted["approval_token"]},
                        headers=agent_headers(token))
    assert first.status_code == 200
    reused = client.post("/v1/ascend/loads/1763/status",
                         json={"status": "Dispatched", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token))
    assert reused.status_code == 403
    assert reused.json()["error_code"] == "approval_consumed"


def test_status_write_stays_dispatched_until_bridge_completes(client):
    token = mint_agent(client)
    minted = mint_status_approval(client, token, "1763", allow_whole_form_save=True)
    posted = client.post("/v1/ascend/loads/1763/status",
                         json={"status": "In Transit", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token))
    assert posted.status_code == 200
    receipt = posted.json()
    assert receipt["status"] == "DISPATCHED"
    assert receipt["requested_status"] == "In Transit"
    claimed = client.get("/v1/portable/writes/pending", headers=agent_headers(token))
    assert claimed.status_code == 200
    job = claimed.json()
    assert job["pending"] is True
    assert job["action"] == "CHANGE_LOAD_STATUS"
    assert job["requested_status"] == "In Transit"
    assert job["allow_whole_form_save"] is True
    completed = client.post(f"/v1/portable/writes/{job['write_id']}/complete",
                            json={"verified": True, "note_present": False, "status_matched": True,
                                  "observed_status": "In Transit",
                                  "live_validated": False, "production_writes": False,
                                  "tab_hint": "scratch:9", "verify_reason": "verified_via_status_readback",
                                  "bridge_version": "0.1.12"},
                            headers=agent_headers(token))
    assert completed.status_code == 200
    body = completed.json()
    assert body["status"] == "VERIFIED"
    assert body["status_matched"] is True
    assert body["observed_status"] == "In Transit"
    assert body["tab_hint"] == "scratch:9"
    assert body["bridge_version"] == "0.1.12"
    assert body["verify_reason"] == "verified_via_status_readback"


def test_verify_without_status_match_is_failed(client):
    token = mint_agent(client)
    minted = mint_status_approval(client, token, "1763")
    posted = client.post("/v1/ascend/loads/1763/status",
                         json={"status": "Delivered", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token)).json()
    client.get("/v1/portable/writes/pending", headers=agent_headers(token))
    completed = client.post(f"/v1/portable/writes/{posted['write_id']}/complete",
                            json={"verified": True, "note_present": False, "status_matched": False,
                                  "observed_status": "Dispatched",
                                  "live_validated": False, "production_writes": False},
                            headers=agent_headers(token))
    assert completed.status_code == 200
    assert completed.json()["status"] == "FAILED"
    assert completed.json()["error_code"] == "verify_without_status_match"
    assert completed.json()["tab_hint"] == "missing"


def test_note_and_status_approvals_do_not_cross(client):
    token = mint_agent(client)
    note = mint_note_approval(client, token, "1763")
    status = mint_status_approval(client, token, "1763", status="Booked")
    crossed = client.post("/v1/ascend/loads/1763/status",
                          json={"status": "Booked", "approval_token": note["approval_token"]},
                          headers=agent_headers(token))
    assert crossed.status_code == 403
    assert crossed.json()["error_code"] == "approval_invalid"
    crossed_note = client.post("/v1/ascend/loads/1763/notes",
                               json={"text": "should not use status token",
                                     "approval_token": status["approval_token"]},
                               headers=agent_headers(token))
    assert crossed_note.status_code == 403
    assert crossed_note.json()["error_code"] == "approval_invalid"


def test_claim_picks_oldest_write_across_note_and_status(client):
    token = mint_agent(client)
    note_mint = mint_note_approval(client, token, "1763")
    status_mint = mint_status_approval(client, token, "1763")
    note = client.post("/v1/ascend/loads/1763/notes",
                       json={"text": "first note", "approval_token": note_mint["approval_token"]},
                       headers=agent_headers(token)).json()
    status = client.post("/v1/ascend/loads/1763/status",
                         json={"status": "Assigned", "approval_token": status_mint["approval_token"]},
                         headers=agent_headers(token)).json()
    first = client.get("/v1/portable/writes/pending", headers=agent_headers(token)).json()
    assert first["write_id"] == note["write_id"]
    assert first["action"] == "ADD_INTERNAL_NOTE"
    second = client.get("/v1/portable/writes/pending", headers=agent_headers(token)).json()
    assert second["write_id"] == note["write_id"]
    client.post(f"/v1/portable/writes/{note['write_id']}/complete",
                json={"verified": False, "note_present": False,
                      "error_code": "NOTE_COMMIT_REQUIRES_OWNER_PATH",
                      "live_validated": False, "production_writes": False},
                headers=agent_headers(token))
    third = client.get("/v1/portable/writes/pending", headers=agent_headers(token)).json()
    assert third["write_id"] == status["write_id"]
    assert third["action"] == "CHANGE_LOAD_STATUS"


def test_via_save_alias_forces_whole_form_flag(client):
    token = mint_agent(client)
    minted = mint_status_approval(client, token, "1763", action="ASCEND_CHANGE_LOAD_STATUS_VIA_SAVE")
    assert minted["allow_whole_form_save"] is True
    posted = client.post("/v1/ascend/loads/1763/status",
                         json={"status": "Booked", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token)).json()
    assert posted["allow_whole_form_save"] is True
    assert posted["commit_kind"] == "WHOLE_FORM_SAVE"
    assert "whole load form" in posted["whole_form_save_risk"]


def test_status_write_requires_session(client):
    client.headers.pop("Authorization", None)
    assert client.post("/v1/ascend/loads/1763/status", json={"status": "Dispatched"}).status_code == 401


def test_unclaimed_status_times_out(client):
    token = mint_agent(client)
    minted = mint_status_approval(client, token, "1763")
    posted = client.post("/v1/ascend/loads/1763/status",
                         json={"status": "Available", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token)).json()
    store = client.app.state.control.store
    record = store.get("booking-logistics", "ascend_status_write", posted["write_id"])
    stale = (utcnow() - timedelta(seconds=120)).isoformat()
    record["created_at"] = stale
    record["dispatched_at"] = stale
    record["claim_deadline_at"] = stale
    store.put("booking-logistics", "ascend_status_write", posted["write_id"], record)
    fetched = client.get(f"/v1/ascend/writes/{posted['write_id']}", headers=agent_headers(token))
    assert fetched.json()["status"] == "FAILED"
    assert fetched.json()["error_code"] == "BRIDGE_CLAIM_TIMEOUT"


def test_harvest_and_note_paths_still_work_with_status_service(client):
    token = mint_agent(client)
    assert client.get("/v1/ascend/status", headers=agent_headers(token)).status_code == 200
    minted = mint_note_approval(client, token, "1763")
    posted = client.post("/v1/ascend/loads/1763/notes",
                         json={"text": "still works", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token))
    assert posted.status_code == 200
    assert posted.json()["status"] == "DISPATCHED"
    assert posted.json()["action"] == "ASCEND_ADD_INTERNAL_NOTE"
    device = sign_in(client)
    empty = client.get("/v1/ascend/loads", headers={"Authorization": f"Bearer {device}"})
    assert empty.status_code == 200


def test_dashboard_exposes_status_approval_controls(client):
    html = client.get("/").text
    assert "mint-status-approval" in html
    assert "status-approval-form" in html
    assert "status-allow-whole-form-save" in html
    assert 'option value="To Be Billed"' in html
    assert client.get("/assets/portable-status.js").status_code == 200
