"""Tests for authentication endpoints."""


def test_auth_status_shows_setup_required(client):
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    assert resp.json()["setup_required"] is True


def test_setup_creates_admin(client):
    resp = client.post("/api/auth/setup", json={"username": "admin", "pin": "1234"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"
    assert "token" in data


def test_setup_rejects_short_pin(client):
    resp = client.post("/api/auth/setup", json={"username": "admin", "pin": "12"})
    assert resp.status_code == 400


def test_setup_rejects_missing_username(client):
    resp = client.post("/api/auth/setup", json={"username": "", "pin": "1234"})
    assert resp.status_code == 400


def test_setup_only_works_once(client):
    client.post("/api/auth/setup", json={"username": "admin", "pin": "1234"})
    resp = client.post("/api/auth/setup", json={"username": "admin2", "pin": "5678"})
    assert resp.status_code == 400


def test_login_succeeds_with_correct_pin(client, admin_token):
    resp = client.post("/api/auth/login", json={"username": "testadmin", "pin": "1234"})
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_login_fails_with_wrong_pin(client, admin_token):
    resp = client.post("/api/auth/login", json={"username": "testadmin", "pin": "9999"})
    assert resp.status_code == 401


def test_login_fails_with_nonexistent_user(client, admin_token):
    resp = client.post("/api/auth/login", json={"username": "nobody", "pin": "1234"})
    assert resp.status_code == 401


def test_token_refresh(client, admin_token):
    resp = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_create_user_requires_admin(client, admin_token):
    # Create a non-admin user
    client.post("/api/auth/create-user",
                json={"username": "rbt1", "pin": "5678", "role": "rbt"},
                headers={"Authorization": f"Bearer {admin_token}"})

    # Login as non-admin
    resp = client.post("/api/auth/login", json={"username": "rbt1", "pin": "5678"})
    rbt_token = resp.json()["token"]

    # Try to create user as non-admin
    resp = client.post("/api/auth/create-user",
                       json={"username": "rbt2", "pin": "0000", "role": "rbt"},
                       headers={"Authorization": f"Bearer {rbt_token}"})
    assert resp.status_code == 403


def test_reset_own_pin(client, admin_token):
    resp = client.post("/api/auth/reset-pin",
                       json={"current_pin": "1234", "new_pin": "5678"},
                       headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["reset"] == "testadmin"

    # Login with new PIN
    resp = client.post("/api/auth/login", json={"username": "testadmin", "pin": "5678"})
    assert resp.status_code == 200


def test_unauthenticated_access_denied(client):
    resp = client.get("/api/providers")
    assert resp.status_code == 401
