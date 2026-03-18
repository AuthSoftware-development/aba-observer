"""Test fixtures for The I — Intelligent Video Analytics."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Set test environment before importing server
os.environ.setdefault("GOOGLE_API_KEY", "test-key-not-real")
os.environ["RATE_LIMIT_ENABLED"] = "false"  # Disable rate limiting in tests


@pytest.fixture(scope="session")
def test_dir():
    """Create a temporary directory for test data."""
    d = tempfile.mkdtemp(prefix="thei_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def client():
    """Create a test client with clean state."""
    # Clean up auth state for each test
    from pathlib import Path
    base = Path(__file__).parent.parent
    users_file = base / ".users.json"
    keys_file = base / ".api_keys.json"

    # Backup and remove
    users_backup = None
    keys_backup = None
    if users_file.exists():
        users_backup = users_file.read_text()
        users_file.unlink()
    if keys_file.exists():
        keys_backup = keys_file.read_text()
        keys_file.unlink()

    from server import app
    with TestClient(app) as c:
        yield c

    # Restore
    if users_backup:
        users_file.write_text(users_backup)
    elif users_file.exists():
        users_file.unlink()
    if keys_backup:
        keys_file.write_text(keys_backup)
    elif keys_file.exists():
        keys_file.unlink()


@pytest.fixture
def admin_token(client):
    """Set up admin and return auth token."""
    resp = client.post("/api/auth/setup", json={"username": "testadmin", "pin": "1234"})
    assert resp.status_code == 200
    return resp.json()["token"]


@pytest.fixture
def auth_headers(admin_token):
    """Return auth headers dict."""
    return {"Authorization": f"Bearer {admin_token}"}
