"""E2E: Search + Platform — index events → search → system status → branding → API keys."""


def test_full_search_flow(client, auth_headers):
    """Index events → search by NL → search by type → check stats."""

    # 1. Index events
    events = [
        {"event_id": "e2e_s1", "domain": "security", "event_type": "possible_fall",
         "description": "Fall near stairwell", "severity": "high"},
        {"event_id": "e2e_s2", "domain": "aba", "event_type": "behavior",
         "description": "Client hand flapping for 10 seconds", "person_name": "Test Client"},
        {"event_id": "e2e_s3", "domain": "retail", "event_type": "crowd_forming",
         "description": "Crowd of 12 at checkout", "severity": "medium"},
    ]
    r = client.post("/api/search/index",
                    json={"events": events},
                    headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json()["indexed"] == 3

    # 2. Natural language search — "falls"
    r = client.post("/api/search/natural",
                    json={"query": "show me all falls"},
                    headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    # 3. Structured search
    r = client.post("/api/search/events",
                    json={"event_type": "behavior", "domain": "aba"},
                    headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200

    # 4. Search stats
    r = client.get("/api/search/stats", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total_events"] >= 3


def test_system_status(client, auth_headers):
    """System status returns platform info, cameras, domains."""
    r = client.get("/api/system/status", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["platform"] == "The I \u2014 Intelligent Video Analytics"
    assert data["version"] == "0.5.0"
    assert "cameras" in data
    assert "domains" in data
    assert "aba" in data["domains"]
    assert "retail" in data["domains"]
    assert "security" in data["domains"]


def test_branding_get_and_update(client, auth_headers):
    """Get branding → update → verify change."""
    # Get default branding (no auth required)
    r = client.get("/api/branding")
    assert r.status_code == 200
    assert r.json()["appName"] == "The I"

    # Update branding (admin only)
    r = client.put("/api/branding",
                   json={"appName": "Custom Brand", "primaryColor": "#ff0000"},
                   headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json()["appName"] == "Custom Brand"
    assert r.json()["primaryColor"] == "#ff0000"

    # Verify persisted
    r = client.get("/api/branding")
    assert r.json()["appName"] == "Custom Brand"

    # Restore default
    r = client.put("/api/branding",
                   json={"appName": "The I", "primaryColor": "#2563eb"},
                   headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200


def test_api_key_lifecycle(client, auth_headers):
    """Create API key → list → revoke → verify revoked."""

    # 1. Create key
    r = client.post("/api/api-keys",
                    json={"name": "E2E Test Key", "scopes": ["/api/pos"]},
                    headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200
    key_id = r.json()["key_id"]
    api_key = r.json()["api_key"]
    assert api_key.startswith("thei_")

    # 2. List keys
    r = client.get("/api/api-keys", headers=auth_headers)
    assert r.status_code == 200
    assert any(k["key_id"] == key_id for k in r.json())

    # 3. Revoke
    r = client.delete(f"/api/api-keys/{key_id}", headers=auth_headers)
    assert r.status_code == 200

    # 4. Verify revoked in list
    r = client.get("/api/api-keys", headers=auth_headers)
    revoked = [k for k in r.json() if k["key_id"] == key_id]
    assert len(revoked) == 1
    assert revoked[0]["revoked"] is True


def test_notification_test_endpoint(client, auth_headers):
    """Test notification delivery through log channel."""
    r = client.post("/api/notifications/test",
                    json={"channel": "log"},
                    headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json()["delivered"]["log"] is True
