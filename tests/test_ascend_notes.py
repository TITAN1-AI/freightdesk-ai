"""Ascend private-internal-note write facade. Not LIVE_VALIDATED."""

from app.models.domain import ActionPolicy
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


def mint_approval(client, token, load_id="1763", text=None):
    body = {"action": "ASCEND_ADD_INTERNAL_NOTE", "load_id": load_id}
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
