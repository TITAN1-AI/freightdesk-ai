"""Ascend read facade over portable harvest. Not a retail API and not LIVE_VALIDATED."""

from tests.test_portable_leases import portable_headers, sign_in, snapshot


def test_facade_empty_harvest_is_clear_not_error(client):
    status = client.get("/v1/ascend/status")
    assert status.status_code == 200
    body = status.json()
    assert body["facade"] == "ascend"
    assert body["source"] == "portable_harvest"
    assert body["not_a_retail_api"] is True
    assert body["live_validated"] is False
    assert body["production_writes"] is False
    assert body["harvest_available"] is False
    assert body["lease_status"] == "NONE"
    assert body["row_count"] == 0
    assert body["extension_last_seen"] is None
    loads = client.get("/v1/ascend/loads")
    assert loads.status_code == 200
    board = loads.json()
    assert board["loads"] == []
    assert board["load_count"] == 0
    assert board["evidence_class"] == "CANDIDATE"
    assert board["live_validated"] is False
    assert board["production_writes"] is False


def test_facade_after_harvest_normalizes_candidate_rows(client):
    token = sign_in(client)
    lease = client.post("/v1/portable/leases", json={"origin": "https://ascendtms.com"},
                        headers=portable_headers(token=token)).json()
    accepted = client.post("/v1/portable/harvest", json=snapshot(lease["id"]),
                           headers=portable_headers(token=lease["lease_token"]))
    assert accepted.status_code == 200
    status = client.get("/v1/ascend/status").json()
    assert status["harvest_available"] is True
    assert status["lease_active"] is True
    assert status["lease_status"] == "ACTIVE"
    assert status["row_count"] == 1
    assert status["harvest_count"] == 1
    assert status["extension_last_seen"]
    board = client.get("/v1/ascend/loads").json()
    assert board["load_count"] == 1
    load = board["loads"][0]
    assert load["load_id"] == "1763"
    assert load["pick_date"] == "09/15/2026"
    assert load["drop_date"] == "09/16/2026"
    assert load["evidence_class"] == "CANDIDATE"
    assert load["fields"]["load_status"] == {"value": "Dispatched", "evidence_class": "CANDIDATE"}
    assert board["live_validated"] is False


def test_facade_keeps_last_harvest_after_revoke(client):
    token = sign_in(client)
    lease = client.post("/v1/portable/leases", json={"origin": "https://ascendtms.com"},
                        headers=portable_headers(token=token)).json()
    client.post("/v1/portable/harvest", json=snapshot(lease["id"]),
                headers=portable_headers(token=lease["lease_token"]))
    revoked = client.post(f"/v1/portable/leases/{lease['id']}/revoke",
                          headers=portable_headers(token=token))
    assert revoked.status_code == 200
    status = client.get("/v1/ascend/status").json()
    assert status["lease_active"] is False
    assert status["lease_status"] == "REVOKED"
    assert status["harvest_available"] is True
    assert status["row_count"] == 1
    board = client.get("/v1/ascend/loads").json()
    assert board["loads"][0]["load_id"] == "1763"
    assert board["lease_status"] == "REVOKED"
    denied = client.post("/v1/portable/harvest", json=snapshot(lease["id"]),
                         headers=portable_headers(token=lease["lease_token"]))
    assert denied.status_code == 403
    assert client.get("/v1/ascend/loads").json()["load_count"] == 1


def test_facade_requires_session(client):
    client.headers.pop("Authorization", None)
    assert client.get("/v1/ascend/status").status_code == 401
    assert client.get("/v1/ascend/loads").status_code == 401


def test_facade_accepts_portable_device_token(client):
    client.headers.pop("Authorization", None)
    token = sign_in(client)
    empty = client.get("/v1/ascend/loads", headers={"Authorization": f"Bearer {token}"})
    assert empty.status_code == 200
    assert empty.json()["loads"] == []
