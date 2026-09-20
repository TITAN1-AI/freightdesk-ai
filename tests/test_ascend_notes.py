"""Ascend private-internal-note write facade. Not LIVE_VALIDATED."""

from datetime import timedelta

from app.models.domain import ActionPolicy, utcnow
from app.services.ascend_notes import json_error_code
from tests.test_agent_sessions import mint_agent
from tests.test_portable_leases import sign_in


def agent_headers(token):
    return {"Authorization": f"Bearer {token}"}


def fixture_executor(store=None):
    ledger = store if store is not None else {}

    def execute(job):
        notes = ledger.setdefault(job["load_id"], [])
        notes.append(job["text"])
        present = job["text"] in notes
        return {"verified": present, "note_present": present, "error_code": None}

    return execute, ledger


def mint_approval(client, token, load_id="1763", text=None, allow_whole_form_save=False,
                  action="ASCEND_ADD_INTERNAL_NOTE"):
    body = {"action": action, "load_id": load_id, "allow_whole_form_save": allow_whole_form_save}
    if text is not None:
        body["text"] = text
    response = client.post("/v1/ascend/approvals", json=body, headers=agent_headers(token))
    assert response.status_code == 200
    minted = response.json()
    assert minted["action"] == "ASCEND_ADD_INTERNAL_NOTE"
    assert minted["one_use"] is True
    assert minted["live_validated"] is False
    assert minted["production_writes"] is False
    assert minted["approval_token"]
    return minted


def test_note_policy_default_is_approval_required(plane):
    assert plane.policy("ASCEND_ADD_INTERNAL_NOTE") == ActionPolicy.APPROVAL_REQUIRED
    assert plane.policy("unknown_ascend_write") == ActionPolicy.FORBIDDEN


def test_note_write_rejected_without_approval(client):
    token = mint_agent(client)
    response = client.post("/v1/ascend/loads/1763/notes", json={"text": "ops check"},
                           headers=agent_headers(token))
    assert response.status_code == 403
    receipt = response.json()
    assert receipt["status"] == "PENDING_APPROVAL"
    assert receipt["action"] == "ASCEND_ADD_INTERNAL_NOTE"
    assert receipt["note_kind"] == "PRIVATE_INTERNAL"
    assert receipt["evidence_class"] == "CANDIDATE"
    assert receipt["live_validated"] is False
    assert receipt["production_writes"] is False
    assert receipt["verified"] is False
    assert receipt["error_code"] == "approval_required"
    assert "ops check" not in str(receipt)
    assert "text" not in receipt


def test_note_write_rejected_with_invalid_approval(client):
    token = mint_agent(client)
    response = client.post("/v1/ascend/loads/1763/notes",
                           json={"text": "ops check", "approval_token": "not-a-real-approval"},
                           headers=agent_headers(token))
    assert response.status_code == 403
    assert response.json()["status"] == "PENDING_APPROVAL"
    assert response.json()["error_code"] == "approval_invalid"


def test_note_write_happy_path_mocked_verify_after_write(client):
    token = mint_agent(client)
    execute, ledger = fixture_executor()
    client.app.state.notes.executor = execute
    minted = mint_approval(client, token, "1763")
    response = client.post("/v1/ascend/loads/1763/notes",
                           json={"text": "internal ops note", "approval_token": minted["approval_token"]},
                           headers=agent_headers(token))
    assert response.status_code == 200
    receipt = response.json()
    assert receipt["status"] == "VERIFIED"
    assert receipt["verified"] is True
    assert receipt["note_present"] is True
    assert receipt["load_id"] == "1763"
    assert receipt["live_validated"] is False
    assert receipt["error_code"] is None
    assert ledger["1763"] == ["internal ops note"]
    assert "internal ops note" not in str(receipt)
    fetched = client.get(f"/v1/ascend/writes/{receipt['write_id']}", headers=agent_headers(token))
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "VERIFIED"


def test_note_approval_is_one_use_and_load_bound(client):
    token = mint_agent(client)
    client.app.state.notes.executor = fixture_executor()[0]
    minted = mint_approval(client, token, "1763")
    wrong = client.post("/v1/ascend/loads/1755/notes",
                        json={"text": "wrong load", "approval_token": minted["approval_token"]},
                        headers=agent_headers(token))
    assert wrong.status_code == 403
    assert wrong.json()["error_code"] == "approval_binding_invalid"
    first = client.post("/v1/ascend/loads/1763/notes",
                        json={"text": "first", "approval_token": minted["approval_token"]},
                        headers=agent_headers(token))
    assert first.status_code == 200
    assert first.json()["status"] == "VERIFIED"
    reused = client.post("/v1/ascend/loads/1763/notes",
                         json={"text": "second", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token))
    assert reused.status_code == 403
    assert reused.json()["error_code"] == "approval_consumed"


def test_note_write_without_executor_stays_dispatched_until_bridge_completes(client):
    token = mint_agent(client)
    minted = mint_approval(client, token, "1763")
    posted = client.post("/v1/ascend/loads/1763/notes",
                         json={"text": "awaiting bridge", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token))
    assert posted.status_code == 200
    receipt = posted.json()
    assert receipt["status"] == "DISPATCHED"
    assert receipt["verified"] is False
    claimed = client.get("/v1/portable/writes/pending", headers=agent_headers(token))
    assert claimed.status_code == 200
    job = claimed.json()
    assert job["pending"] is True
    assert job["action"] == "ADD_INTERNAL_NOTE"
    assert job["text"] == "awaiting bridge"
    assert job["load_id"] == "1763"
    completed = client.post(f"/v1/portable/writes/{job['write_id']}/complete",
                            json={"verified": True, "note_present": True,
                                  "live_validated": False, "production_writes": False},
                            headers=agent_headers(token))
    assert completed.status_code == 200
    assert completed.json()["status"] == "VERIFIED"
    assert completed.json()["note_present"] is True


def test_verify_without_presence_is_failed_not_success(client):
    token = mint_agent(client)
    minted = mint_approval(client, token, "1763")
    posted = client.post("/v1/ascend/loads/1763/notes",
                         json={"text": "missing readback", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token)).json()
    completed = client.post(f"/v1/portable/writes/{posted['write_id']}/complete",
                            json={"verified": True, "note_present": False,
                                  "live_validated": False, "production_writes": False},
                            headers=agent_headers(token))
    assert completed.status_code == 200
    assert completed.json()["status"] == "FAILED"
    assert completed.json()["error_code"] == "verify_without_presence"
    assert completed.json()["verified"] is False


def test_note_write_requires_session_and_rejects_empty_text(client):
    client.headers.pop("Authorization", None)
    assert client.post("/v1/ascend/loads/1763/notes", json={"text": "x"}).status_code == 401
    token = mint_agent(client)
    minted = mint_approval(client, token)
    empty = client.post("/v1/ascend/loads/1763/notes",
                        json={"text": "   ", "approval_token": minted["approval_token"]},
                        headers=agent_headers(token))
    assert empty.status_code == 409
    other = client.post("/v1/ascend/approvals",
                        json={"action": "update_status", "load_id": "1763"},
                        headers=agent_headers(token))
    assert other.status_code == 409


def test_dashboard_exposes_note_approval_controls(client):
    html = client.get("/").text
    assert "mint-note-approval" in html
    assert "note-approval-form" in html
    assert "note-allow-whole-form-save" in html
    assert client.get("/assets/portable-notes.js").status_code == 200


def test_owner_dashboard_can_mint_note_approval(client):
    minted = client.post("/v1/ascend/approvals",
                         json={"action": "ASCEND_ADD_INTERNAL_NOTE", "load_id": "1763"})
    assert minted.status_code == 200
    assert minted.json()["approval_token"]
    assert minted.json()["how"]


def test_harvest_and_agent_bearer_paths_still_work(client):
    token = mint_agent(client)
    status = client.get("/v1/ascend/status", headers=agent_headers(token))
    assert status.status_code == 200
    assert status.json()["production_writes"] is False
    device = sign_in(client)
    empty = client.get("/v1/ascend/loads", headers={"Authorization": f"Bearer {device}"})
    assert empty.status_code == 200
    assert empty.json()["loads"] == []


def test_note_text_is_not_audited(client):
    token = mint_agent(client)
    client.app.state.notes.executor = fixture_executor()[0]
    minted = mint_approval(client, token, "1763")
    secret = "unique-private-note-text-xyz"
    client.post("/v1/ascend/loads/1763/notes",
                json={"text": secret, "approval_token": minted["approval_token"]},
                headers=agent_headers(token))
    timeline = client.app.state.control.store.timeline("booking-logistics", limit=50)
    dumped = str(timeline)
    assert secret not in dumped
    assert "ASCEND_NOTE_VERIFIED" in dumped or any(
        item.get("event") == "ASCEND_NOTE_VERIFIED" for item in timeline)


def test_bridge_complete_keeps_opener_and_commit_diagnostics(client):
    token = mint_agent(client)
    minted = mint_approval(client, token, "1763")
    posted = client.post("/v1/ascend/loads/1763/notes",
                         json={"text": "field fail receipt", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token)).json()
    claimed = client.get("/v1/portable/writes/pending", headers=agent_headers(token))
    assert claimed.json()["pending"] is True
    completed = client.post(f"/v1/portable/writes/{posted['write_id']}/complete",
                            json={"verified": False, "note_present": False,
                                  "error_code": "NOTE_COMMIT_REQUIRES_OWNER_PATH",
                                  "live_validated": False, "production_writes": False,
                                  "stage": "inspect", "opener_strategy": "already_open",
                                  "note_label": "Private Load Note", "commit_kind": "WHOLE_FORM_SAVE",
                                  "tab_hint": "scratch:9;skip=board:8"},
                            headers=agent_headers(token))
    assert completed.status_code == 200
    receipt = completed.json()
    assert receipt["status"] == "FAILED"
    assert receipt["error_code"] == "NOTE_COMMIT_REQUIRES_OWNER_PATH"
    assert receipt["stage"] == "inspect"
    assert receipt["opener_strategy"] == "already_open"
    assert receipt["note_label"] == "Private Load Note"
    assert receipt["commit_kind"] == "WHOLE_FORM_SAVE"
    assert receipt["tab_hint"] == "scratch:9;skip=board:8"
    assert receipt["verified"] is False
    assert "field fail receipt" not in str(receipt)
    fetched = client.get(f"/v1/ascend/writes/{posted['write_id']}", headers=agent_headers(token))
    assert fetched.json()["error_code"] == "NOTE_COMMIT_REQUIRES_OWNER_PATH"
    assert fetched.json()["opener_strategy"] == "already_open"
    assert fetched.json()["allow_whole_form_save"] is False


def test_whole_form_save_requires_approval_flag(client):
    token = mint_agent(client)
    minted = mint_approval(client, token, "1763")
    assert minted["allow_whole_form_save"] is False
    posted = client.post("/v1/ascend/loads/1763/notes",
                         json={"text": "needs owner path", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token)).json()
    assert posted["status"] == "DISPATCHED"
    assert posted["allow_whole_form_save"] is False
    claimed = client.get("/v1/portable/writes/pending", headers=agent_headers(token)).json()
    assert claimed["allow_whole_form_save"] is False
    assert claimed["text"] == "needs owner path"


def test_whole_form_save_approval_flag_dispatches_mock_save_path(client):
    token = mint_agent(client)
    ledger = {}

    def execute(job):
        assert job["allow_whole_form_save"] is True
        notes = ledger.setdefault(job["load_id"], [])
        notes.append(job["text"])
        return {
            "verified": True,
            "note_present": True,
            "error_code": None,
            "commit_kind": "WHOLE_FORM_SAVE",
            "save_variant": "SAVE_STAY",
            "note_label": "scratch",
            "stage": "verify",
        }

    client.app.state.notes.executor = execute
    minted = mint_approval(client, token, "1763", allow_whole_form_save=True)
    assert minted["allow_whole_form_save"] is True
    assert minted["commit_kind"] == "WHOLE_FORM_SAVE"
    assert "textarea#scratch" in minted["whole_form_save_risk"]
    response = client.post("/v1/ascend/loads/1763/notes",
                           json={"text": "scratch via save", "approval_token": minted["approval_token"]},
                           headers=agent_headers(token))
    assert response.status_code == 200
    receipt = response.json()
    assert receipt["status"] == "VERIFIED"
    assert receipt["note_present"] is True
    assert receipt["allow_whole_form_save"] is True
    assert receipt["commit_kind"] == "WHOLE_FORM_SAVE"
    assert receipt["save_variant"] == "SAVE_STAY"
    assert "textarea#scratch" in receipt["whole_form_save_risk"]
    assert "scratch via save" not in str(receipt)
    assert ledger["1763"] == ["scratch via save"]


def test_via_save_action_is_alias_for_whole_form_flag(client):
    token = mint_agent(client)
    minted = mint_approval(client, token, "1763", action="ASCEND_ADD_INTERNAL_NOTE_VIA_SAVE")
    assert minted["action"] == "ASCEND_ADD_INTERNAL_NOTE"
    assert minted["allow_whole_form_save"] is True
    claimed_posted = client.post("/v1/ascend/loads/1763/notes",
                                 json={"text": "via save alias", "approval_token": minted["approval_token"]},
                                 headers=agent_headers(token)).json()
    assert claimed_posted["status"] == "DISPATCHED"
    assert claimed_posted["allow_whole_form_save"] is True
    claimed = client.get("/v1/portable/writes/pending", headers=agent_headers(token)).json()
    assert claimed["allow_whole_form_save"] is True
    assert claimed["text"] == "via save alias"


def test_bridge_can_reclaim_incomplete_dispatch(client):
    token = mint_agent(client)
    minted = mint_approval(client, token, "1763")
    posted = client.post("/v1/ascend/loads/1763/notes",
                         json={"text": "retry claim", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token)).json()
    assert posted["status"] == "DISPATCHED"
    assert posted["claimed_at"] is None
    assert posted["stage"] == "awaiting_bridge"
    first = client.get("/v1/portable/writes/pending", headers=agent_headers(token)).json()
    assert first["pending"] is True
    assert first["write_id"] == posted["write_id"]
    after = client.get(f"/v1/ascend/writes/{posted['write_id']}", headers=agent_headers(token)).json()
    assert after["status"] == "DISPATCHED"
    assert after["claimed_at"]
    assert after["stage"] == "claimed"
    second = client.get("/v1/portable/writes/pending", headers=agent_headers(token)).json()
    assert second["pending"] is True
    assert second["write_id"] == posted["write_id"]
    assert second["text"] == "retry claim"


def test_unclaimed_dispatch_times_out_as_bridge_claim_timeout(client):
    token = mint_agent(client)
    minted = mint_approval(client, token, "1763")
    posted = client.post("/v1/ascend/loads/1763/notes",
                         json={"text": "never claimed", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token)).json()
    store = client.app.state.control.store
    record = store.get("booking-logistics", "ascend_note_write", posted["write_id"])
    stale = (utcnow() - timedelta(seconds=120)).isoformat()
    record["created_at"] = stale
    record["dispatched_at"] = stale
    record["claim_deadline_at"] = stale
    store.put("booking-logistics", "ascend_note_write", posted["write_id"], record)
    fetched = client.get(f"/v1/ascend/writes/{posted['write_id']}", headers=agent_headers(token))
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "FAILED"
    assert fetched.json()["error_code"] == "BRIDGE_CLAIM_TIMEOUT"
    assert fetched.json()["verified"] is False
    empty = client.get("/v1/portable/writes/pending", headers=agent_headers(token)).json()
    assert empty["pending"] is False


def test_complete_coerces_object_error_code(client):
    token = mint_agent(client)
    minted = mint_approval(client, token, "1763")
    posted = client.post("/v1/ascend/loads/1763/notes",
                         json={"text": "object code", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token)).json()
    client.get("/v1/portable/writes/pending", headers=agent_headers(token))
    completed = client.post(
        f"/v1/portable/writes/{posted['write_id']}/complete",
        json={"verified": False, "note_present": False,
              "error_code": {"msg": "NOTE_COMMIT_REQUIRES_OWNER_PATH", "loc": ["body"]},
              "live_validated": False, "production_writes": False,
              "stage": "inspect", "commit_kind": "WHOLE_FORM_SAVE"},
        headers=agent_headers(token))
    assert completed.status_code == 200
    assert completed.json()["error_code"] == "NOTE_COMMIT_REQUIRES_OWNER_PATH"
    assert json_error_code([{"msg": "NOTE_COMMIT_REQUIRES_OWNER_PATH"}]) == "NOTE_COMMIT_REQUIRES_OWNER_PATH"


def test_complete_accepts_bridge_extra_fields_without_422(client):
    token = mint_agent(client)
    minted = mint_approval(client, token, "1763")
    posted = client.post("/v1/ascend/loads/1763/notes",
                         json={"text": "extra field", "approval_token": minted["approval_token"]},
                         headers=agent_headers(token)).json()
    client.get("/v1/portable/writes/pending", headers=agent_headers(token))
    completed = client.post(
        f"/v1/portable/writes/{posted['write_id']}/complete",
        json={"verified": False, "note_present": False,
              "error_code": "NOTE_COMMIT_REQUIRES_OWNER_PATH",
              "live_validated": False, "production_writes": False,
              "stage": "inspect", "opener_strategy": "already_open",
              "commit_kind": "WHOLE_FORM_SAVE",
              "allow_whole_form_save": False,
              "unknown_future_field": "ignore-me"},
        headers=agent_headers(token))
    assert completed.status_code == 200
    receipt = completed.json()
    assert receipt["status"] == "FAILED"
    assert receipt["error_code"] == "NOTE_COMMIT_REQUIRES_OWNER_PATH"
    assert receipt["claimed_at"]
    fetched = client.get(f"/v1/ascend/writes/{posted['write_id']}", headers=agent_headers(token)).json()
    assert fetched["status"] == "FAILED"
    assert fetched["claimed_at"]
    assert fetched["error_code"] == "NOTE_COMMIT_REQUIRES_OWNER_PATH"
