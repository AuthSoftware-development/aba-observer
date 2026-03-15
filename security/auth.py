"""JWT-based PIN authentication for HIPAA access control."""

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

# Session timeout in seconds (15 minutes of inactivity)
SESSION_TIMEOUT = 900

_USERS_FILE = Path(__file__).parent.parent / ".users.json"
_JWT_SECRET_FILE = Path(__file__).parent.parent / ".jwt_secret"


def _get_jwt_secret() -> str:
    """Get or generate JWT signing secret."""
    if _JWT_SECRET_FILE.exists():
        return _JWT_SECRET_FILE.read_text().strip()
    secret = secrets.token_hex(32)
    _JWT_SECRET_FILE.write_text(secret)
    try:
        os.chmod(str(_JWT_SECRET_FILE), 0o600)
    except OSError:
        pass
    return secret


def _hash_pin(pin: str, salt: str) -> str:
    """Hash a PIN with salt using SHA-256 (iterated)."""
    # PBKDF2-like: iterate SHA-256 10000 times
    h = (pin + salt).encode()
    for _ in range(10000):
        h = hashlib.sha256(h).digest()
    return h.hex()


def _load_users() -> dict:
    """Load user database."""
    if _USERS_FILE.exists():
        with open(_USERS_FILE) as f:
            return json.load(f)
    return {}


def _save_users(users: dict):
    """Save user database."""
    with open(_USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    try:
        os.chmod(str(_USERS_FILE), 0o600)
    except OSError:
        pass


def setup_required() -> bool:
    """Check if initial setup (first user) is needed."""
    users = _load_users()
    return len(users) == 0


def create_user(username: str, pin: str, role: str = "bcba") -> bool:
    """Create a new user with a PIN. Returns True if created."""
    users = _load_users()
    if username in users:
        return False
    salt = secrets.token_hex(16)
    users[username] = {
        "pin_hash": _hash_pin(pin, salt),
        "salt": salt,
        "role": role,  # bcba, rbt, admin
        "created_at": time.time(),
    }
    _save_users(users)
    return True


def verify_pin(username: str, pin: str) -> dict | None:
    """Verify a user's PIN. Returns user info or None."""
    users = _load_users()
    user = users.get(username)
    if not user:
        return None
    expected = _hash_pin(pin, user["salt"])
    if not hmac.compare_digest(expected, user["pin_hash"]):
        return None
    return {"username": username, "role": user["role"]}


def create_token(username: str, role: str) -> str:
    """Create a simple HMAC-signed JWT-like token."""
    secret = _get_jwt_secret()
    payload = {
        "sub": username,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + SESSION_TIMEOUT,
    }
    import base64
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token: str) -> dict | None:
    """Verify and decode a token. Returns payload or None."""
    if not token or "." not in token:
        return None
    try:
        import base64
        payload_b64, sig = token.rsplit(".", 1)
        secret = _get_jwt_secret()
        expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def refresh_token(token: str) -> str | None:
    """Refresh a valid token (extend expiry). Returns new token or None."""
    payload = verify_token(token)
    if not payload:
        return None
    return create_token(payload["sub"], payload["role"])
