"""Capability map, load-by-id facade, and write stubs. Not LIVE_VALIDATED."""

from app.services.ascend_atlas import (
    PRIVATE_NOTE_SELECTOR,
    PUBLIC_NOTE_SELECTOR,
    WHOLE_FORM_SAVE,
    atlas_field,
    harvest_load_statuses,
    load_atlas,
    load_capabilities,
    require_atlas_bindings,
    status_catalog,
    write_statuses,
)
from app.services.ascend_status import WRITE_STATUSES
from app.services.portable_leases import LOAD_STATUSES
from tests.test_portable_leases import portable_headers, sign_in, snapshot


def _harvest(client):
    token = sign_in(client)
    lease = client.post("/v1/portable/leases", json={"origin": "https://ascendtms.com"},
                        headers=portable_headers(token=token)).json()
    accepted = client.post("/v1/portable/harvest", json=snapshot(lease["id"]),
                           headers=portable_headers(token=lease["lease_token"]))
    assert accepted.status_code == 200
    return lease


def test_atlas_wires_scratch_and_load_basics():
    require_atlas_bindings()
    atlas = load_atlas()
    assert atlas["section"] == "Load Basics"
    assert atlas["live_validated"] is False
    assert atlas["production_writes"] is False
    private = atlas_field("private_notes")
    assert private["selector"] == PRIVATE_NOTE_SELECTOR
    assert private["id"] == "scratch"
    assert private["write_method"] == WHOLE_FORM_SAVE
    assert private["policy"] == "APPROVAL_REQUIRED"
    public = atlas_field("public_notes")
    assert public["selector"] == PUBLIC_NOTE_SELECTOR
    assert public["policy"] == "FORBIDDEN"
    for name in ("load_id", "load_status", "pick_date", "drop_date"):
        assert atlas_field(name)["section"] == "Load Basics"
    catalog = load_capabilities()
    assert catalog["next_live_field_after_note_verified"] == "write_status"
    assert catalog["capabilities"]["write_status"]["policy"] == "APPROVAL_REQUIRED"
    assert catalog["capabilities"]["write_status"]["implementation"] == "IMPLEMENTED"
    assert catalog["capabilities"]["assign_carrier"]["policy"] == "FORBIDDEN"
    assert catalog["capabilities"]["write_expenses"]["policy"] == "FORBIDDEN"
    assert catalog["capabilities"]["write_public_note"]["implementation"] == "FORBIDDEN"
    expected = list(status_catalog())
    assert "To Be Billed" in expected
    assert "UNKNOWN" not in expected
    assert atlas_field("load_status")["allowed_values"] == expected
    assert catalog["capabilities"]["write_status"]["allowed_statuses"] == expected
    assert write_statuses() == WRITE_STATUSES == frozenset(expected)
    assert LOAD_STATUSES == harvest_load_statuses() == frozenset({*expected, "UNKNOWN"})


def test_status_catalog_is_atlas_derived_and_served(client):
    expected = list(status_catalog())
    body = client.get("/v1/ascend/capabilities").json()
    assert body["atlas"]["status_catalog"] == expected
    assert body["capabilities"]["write_status"]["allowed_statuses"] == expected
    assert "To Be Billed" in body["capabilities"]["write_status"]["allowed_statuses"]
    html = client.get("/").text
    assert 'option value="To Be Billed"' in html
    assert 'option value="Driver Assigned"' in html


def test_capability_catalog_is_demo_gated_and_not_live(client):
    body = client.get("/v1/ascend/capabilities").json()
    assert body["facade"] == "ascend"
    assert body["live_validated"] is False
    assert body["production_writes"] is False
    assert body["not_a_retail_api"] is True
    assert body["atlas"]["private_note_selector"] == "textarea#scratch"
    assert body["atlas"]["public_note_selector"] == "#notes"
    assert body["atlas"]["commit_kind"] == "WHOLE_FORM_SAVE"
    assert "write_status" in body["capabilities"]
    assert body["capabilities"]["write_private_note"]["implementation"] == "IMPLEMENTED"
    assert body["capabilities"]["write_status"]["implementation"] == "IMPLEMENTED"
    assert body["capabilities"]["write_status"]["live_validated"] is False
    assert body["next_live_field_after_note_verified"] == "write_status"


def test_load_by_id_empty_harvest_is_safe(client):
    missing = client.get("/v1/ascend/loads/1763")
    assert missing.status_code == 200
    body = missing.json()
    assert body["load_id"] == "1763"
    assert body["found"] is False
    assert body["harvest_available"] is False
    assert body["fields"] == {}
    assert body["live_validated"] is False
    assert body["production_writes"] is False
    assert body["section"] == "Load Basics"
    assert "private_notes" in body["atlas_fields"]


def test_load_by_id_returns_harvested_candidate_fields(client):
    _harvest(client)
    found = client.get("/v1/ascend/loads/1763").json()
    assert found["found"] is True
    assert found["harvest_available"] is True
    assert found["pick_date"] == "09/15/2026"
    assert found["drop_date"] == "09/16/2026"
    assert found["fields"]["load_status"] == {"value": "Dispatched", "evidence_class": "CANDIDATE"}
    assert found["evidence_class"] == "CANDIDATE"
    unknown = client.get("/v1/ascend/loads/1755")
    assert unknown.status_code == 200
    assert unknown.json()["found"] is False
    assert unknown.json()["harvest_available"] is True
    assert unknown.json()["fields"] == {}


def test_load_by_id_rejects_invalid_identity(client):
    assert client.get("/v1/ascend/loads/not-a-load").status_code == 409
    assert client.get("/v1/ascend/loads/" + "1" * 21).status_code == 409


def test_status_write_is_approval_required_not_a_stub(client):
    response = client.post("/v1/ascend/loads/1763/status", json={"status": "Dispatched"})
    assert response.status_code == 403
    body = response.json()
    assert body["status"] == "PENDING_APPROVAL"
    assert body["action"] == "ASCEND_CHANGE_LOAD_STATUS"
    assert body["policy"] == "APPROVAL_REQUIRED"
    assert body["silent_save_forbidden"] is True
    assert body["production_writes"] is False
    assert body["live_validated"] is False
    assert body["requested_status"] == "Dispatched"
    flagged = client.post("/v1/ascend/loads/1763/status",
                          json={"status": "Dispatched", "approval_token": "x" * 32})
    assert flagged.status_code == 403
    assert flagged.json()["error_code"] == "approval_invalid"


def test_assign_and_expenses_are_forbidden_stubs(client):
    assign = client.post("/v1/ascend/loads/1763/assign", json={})
    assert assign.status_code == 403
    assert assign.json()["result"] == "FORBIDDEN"
    assert assign.json()["capability"] == "assign_carrier"
    assert assign.json()["policy"] == "FORBIDDEN"
    expenses = client.post("/v1/ascend/loads/1763/expenses", json={})
    assert expenses.status_code == 403
    assert expenses.json()["capability"] == "write_expenses"
    assert expenses.json()["silent_save_forbidden"] is True


def test_write_stubs_and_load_by_id_require_session(client):
    client.headers.pop("Authorization", None)
    assert client.get("/v1/ascend/capabilities").status_code == 401
    assert client.get("/v1/ascend/loads/1763").status_code == 401
    assert client.post("/v1/ascend/loads/1763/status", json={"status": "Dispatched"}).status_code == 401
    assert client.post("/v1/ascend/loads/1763/assign", json={}).status_code == 401


def test_existing_board_and_agent_paths_stay_intact(client):
    _harvest(client)
    board = client.get("/v1/ascend/loads").json()
    assert board["load_count"] == 1
    assert board["loads"][0]["load_id"] == "1763"
    status = client.get("/v1/ascend/status").json()
    assert status["harvest_available"] is True
    assert status["production_writes"] is False
    from tests.test_agent_sessions import mint_agent
    token = mint_agent(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/v1/ascend/loads/1763", headers=headers).json()["found"] is True
    assert client.get("/v1/ascend/capabilities", headers=headers).status_code == 200
    stub = client.post("/v1/ascend/loads/1763/status", json={"status": "Dispatched"}, headers=headers)
    assert stub.status_code == 403
    assert stub.json()["status"] == "PENDING_APPROVAL"
