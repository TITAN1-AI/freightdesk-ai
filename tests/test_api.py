def test_dashboard_assets_and_snapshot(client):
    assert client.get("/").status_code == 200
    assert client.get("/assets/app.js").status_code == 200
    response = client.get("/api/snapshot")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo" and not data["live_validated"]
    assert len(data["shipments"]) == 4
    assert all(s["demo"] and s["id"].startswith("DEMO-") for s in data["shipments"])
    assert not any(c["live_validated"] for c in data["connections"])
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_auth_required_and_safe_bootstrap(client):
    client.headers.pop("Authorization")
    assert client.get("/api/snapshot").status_code == 401
    assert client.post("/api/session").status_code == 403
    assert client.post("/api/session", headers={"X-FreightDesk-Local": "1"}).status_code == 200
    assert client.get("/api/snapshot").status_code == 200
    assert client.post("/api/commands", json={"command": "status 1847"}).status_code == 403
    assert client.post("/api/commands", headers={"X-FreightDesk-Local": "1"},
                       json={"command": "status 1847"}).status_code == 200


def test_cross_origin_and_host_rejected(client):
    assert client.post("/api/session", headers={"Origin": "https://evil.example",
        "X-FreightDesk-Local": "1"}).status_code == 403
    assert client.get("/api/snapshot", headers={"Host": "evil.example"}).status_code == 400


def test_owner_cannot_spoof_tenant_or_role_in_request(client):
    response = client.post("/api/commands", json={"command": "status 1847", "role": "OWNER"})
    assert response.status_code == 422
    assert client.post("/api/events", json={"tenant_id": "other", "shipment_id": "DEMO-1847",
        "kind": "REVIEW", "source": "dashboard"}).status_code == 403


def test_demo_endpoint_is_not_a_vendor_webhook(client):
    assert client.post("/api/events", json={"tenant_id": "booking-logistics", "shipment_id": "DEMO-1847",
        "kind": "REVIEW", "source": "carrierview"}).status_code == 422


def test_api_pause_resume_and_policy(client):
    assert client.post("/api/pause", json={"paused": True}).status_code == 200
    assert client.post("/api/commands", json={"command": "review 1847"}).status_code == 409
    assert client.post("/api/pause", json={"paused": False}).status_code == 200
    assert client.post("/api/commands", json={"command": "review 1847"}).status_code == 200
    assert client.post("/api/policies", json={"action": "routine_customer_update",
                                            "policy": "ALLOW"}).status_code == 200
    assert client.post("/api/actions", json={"action": "routine_customer_update",
        "shipment_id": "DEMO-1847", "request_id": "api-request-001"}).json()["status"] == "SIMULATED"


def test_missing_load_and_unsupported_command(client):
    assert client.get("/api/shipments/not-a-load").status_code == 404
    assert client.post("/api/commands", json={"command": "pay carrier"}).status_code == 409
