"""E2E: Security flow — alert rules → access control → tailgating → compliance."""


def test_full_security_flow(client, auth_headers):
    """Create alert rules → send access events → detect tailgating → check compliance."""

    # 1. Create alert rule
    r = client.post("/api/security/alerts",
                    json={
                        "name": "E2E Fall Alert",
                        "event_type": "possible_fall",
                        "severity_min": "high",
                        "notify": ["log"],
                    },
                    headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200
    rule_id = r.json()["rule_id"]

    # 2. List rules
    r = client.get("/api/security/alerts", headers=auth_headers)
    assert r.status_code == 200
    assert any(rule["rule_id"] == rule_id for rule in r.json())

    # 3. Send access control events (rapid entries = tailgating)
    import time
    for i in range(2):
        r = client.post("/api/access-control/webhook",
                        json={
                            "door_id": "e2e-door",
                            "badge_id": f"badge-{i}",
                            "event_type": "entry",
                            "person_name": f"Employee {i}",
                            "timestamp": time.time() + i,  # 1 second apart
                        },
                        headers={**auth_headers, "Content-Type": "application/json"})
        assert r.status_code == 200

    # 4. Check access events recorded
    r = client.get("/api/access-control/events", headers=auth_headers)
    assert r.status_code == 200
    assert any(e.get("door_id") == "e2e-door" for e in r.json())

    # 5. Detect tailgating
    r = client.get("/api/access-control/tailgating", headers=auth_headers)
    assert r.status_code == 200
    tailgating = [t for t in r.json() if t.get("door_id") == "e2e-door"]
    assert len(tailgating) >= 1

    # 6. Check compliance — HIPAA should be on by default
    r = client.get("/api/compliance", headers=auth_headers)
    assert r.status_code == 200
    config = r.json()
    assert config["hipaa"]["enabled"] is True

    # 7. Enable BIPA → face recognition should be blocked
    r = client.put("/api/compliance/bipa",
                   json={"enabled": True},
                   headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200

    r = client.post("/api/compliance/check",
                    json={"action": "face_recognition"},
                    headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json()["allowed"] is False

    # 8. Disable BIPA → face recognition allowed again
    r = client.put("/api/compliance/bipa",
                   json={"enabled": False},
                   headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200

    r = client.post("/api/compliance/check",
                    json={"action": "face_recognition"},
                    headers={**auth_headers, "Content-Type": "application/json"})
    assert r.json()["allowed"] is True

    # 9. Delete alert rule
    r = client.delete(f"/api/security/alerts/{rule_id}", headers=auth_headers)
    assert r.status_code == 200


def test_alert_rule_requires_admin(client, auth_headers):
    """Non-admin users cannot create alert rules."""
    # Create non-admin
    client.post("/api/auth/create-user",
                json={"username": "e2e_rbt2", "pin": "1234", "role": "rbt"},
                headers={**auth_headers, "Content-Type": "application/json"})

    r = client.post("/api/auth/login", json={"username": "e2e_rbt2", "pin": "1234"})
    rbt_headers = {"Authorization": f"Bearer {r.json()['token']}"}

    r = client.post("/api/security/alerts",
                    json={"name": "Fail", "event_type": "test"},
                    headers={**rbt_headers, "Content-Type": "application/json"})
    assert r.status_code == 403
