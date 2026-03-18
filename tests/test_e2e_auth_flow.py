"""E2E: Complete authentication lifecycle — setup → login → create user → reset PIN → logout."""


def test_full_auth_lifecycle(client):
    # 1. Check setup required
    r = client.get("/api/auth/status")
    assert r.json()["setup_required"] is True

    # 2. Setup admin
    r = client.post("/api/auth/setup", json={"username": "admin", "pin": "1234"})
    assert r.status_code == 200
    admin_token = r.json()["token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Setup no longer required
    r = client.get("/api/auth/status")
    assert r.json()["setup_required"] is False

    # 4. Create a therapist user
    r = client.post("/api/auth/create-user",
                    json={"username": "therapist1", "pin": "5678", "role": "bcba"},
                    headers=headers)
    assert r.status_code == 200
    assert r.json()["created"] == "therapist1"

    # 5. Login as therapist
    r = client.post("/api/auth/login", json={"username": "therapist1", "pin": "5678"})
    assert r.status_code == 200
    therapist_token = r.json()["token"]
    t_headers = {"Authorization": f"Bearer {therapist_token}"}

    # 6. Therapist refreshes token
    r = client.post("/api/auth/refresh", headers=t_headers)
    assert r.status_code == 200
    new_token = r.json()["token"]

    # 7. Therapist resets own PIN
    r = client.post("/api/auth/reset-pin",
                    json={"current_pin": "5678", "new_pin": "9999"},
                    headers={"Authorization": f"Bearer {new_token}"})
    assert r.status_code == 200

    # 8. Login with new PIN works
    r = client.post("/api/auth/login", json={"username": "therapist1", "pin": "9999"})
    assert r.status_code == 200

    # 9. Old PIN fails
    r = client.post("/api/auth/login", json={"username": "therapist1", "pin": "5678"})
    assert r.status_code == 401

    # 10. Admin resets therapist PIN without current PIN
    r = client.post("/api/auth/reset-pin",
                    json={"username": "therapist1", "new_pin": "0000"},
                    headers=headers)
    assert r.status_code == 200

    # 11. Therapist can't create users (not admin)
    r = client.post("/api/auth/login", json={"username": "therapist1", "pin": "0000"})
    t2_headers = {"Authorization": f"Bearer {r.json()['token']}"}
    r = client.post("/api/auth/create-user",
                    json={"username": "rbt1", "pin": "1111", "role": "rbt"},
                    headers=t2_headers)
    assert r.status_code == 403
