"""API key management for third-party integrations.

API keys provide stateless authentication for external systems (POS,
access control, custom integrations) without requiring PIN-based login.
"""

import hashlib
import json
import os
import secrets
import time
from pathlib import Path

API_KEYS_FILE = Path(__file__).parent.parent / ".api_keys.json"


def _load_keys() -> dict:
    if API_KEYS_FILE.exists():
        with open(API_KEYS_FILE) as f:
            return json.load(f)
    return {}


def _save_keys(keys: dict):
    with open(API_KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)
    try:
        os.chmod(str(API_KEYS_FILE), 0o600)
    except OSError:
        pass


def create_api_key(
    name: str,
    created_by: str,
    scopes: list[str] | None = None,
    expires_at: float | None = None,
) -> dict:
    """Create a new API key.

    Args:
        name: Human-readable name (e.g., "Square POS Integration")
        created_by: Username who created the key
        scopes: List of allowed endpoint prefixes (e.g., ["/api/pos", "/api/access-control"])
                None = all endpoints
        expires_at: Unix timestamp for expiration (None = no expiry)

    Returns:
        Dict with key_id, api_key (only shown once), and metadata
    """
    keys = _load_keys()

    key_id = secrets.token_hex(8)
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    keys[key_id] = {
        "key_id": key_id,
        "key_hash": key_hash,
        "name": name,
        "created_by": created_by,
        "scopes": scopes,
        "expires_at": expires_at,
        "created_at": time.time(),
        "last_used": None,
        "use_count": 0,
        "revoked": False,
    }

    _save_keys(keys)

    return {
        "key_id": key_id,
        "api_key": f"thei_{key_id}_{raw_key}",  # Full key — shown only once
        "name": name,
        "scopes": scopes,
        "expires_at": expires_at,
    }


def verify_api_key(api_key: str, endpoint: str = "") -> dict | None:
    """Verify an API key and check scope.

    Args:
        api_key: Full API key string (thei_<key_id>_<secret>)
        endpoint: The endpoint being accessed (for scope checking)

    Returns:
        Key metadata if valid, None if invalid
    """
    if not api_key or not api_key.startswith("thei_"):
        return None

    parts = api_key.split("_", 2)
    if len(parts) != 3:
        return None

    _, key_id, raw_key = parts
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    keys = _load_keys()
    key_data = keys.get(key_id)

    if not key_data:
        return None
    if key_data.get("revoked"):
        return None
    if key_data["key_hash"] != key_hash:
        return None
    if key_data.get("expires_at") and key_data["expires_at"] < time.time():
        return None

    # Check scope
    scopes = key_data.get("scopes")
    if scopes and endpoint:
        if not any(endpoint.startswith(s) for s in scopes):
            return None

    # Update usage stats
    key_data["last_used"] = time.time()
    key_data["use_count"] += 1
    _save_keys(keys)

    return {
        "key_id": key_id,
        "name": key_data["name"],
        "created_by": key_data["created_by"],
        "scopes": key_data["scopes"],
    }


def list_api_keys() -> list[dict]:
    """List all API keys (without hashes)."""
    keys = _load_keys()
    return [
        {
            "key_id": k["key_id"],
            "name": k["name"],
            "created_by": k["created_by"],
            "scopes": k["scopes"],
            "created_at": k["created_at"],
            "last_used": k["last_used"],
            "use_count": k["use_count"],
            "revoked": k["revoked"],
            "expires_at": k.get("expires_at"),
        }
        for k in keys.values()
    ]


def revoke_api_key(key_id: str) -> bool:
    """Revoke an API key."""
    keys = _load_keys()
    if key_id not in keys:
        return False
    keys[key_id]["revoked"] = True
    _save_keys(keys)
    return True
