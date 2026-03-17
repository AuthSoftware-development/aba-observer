"""Consent-based face recognition storage with encrypted embeddings.

All face embeddings are encrypted at rest with a separate key from general data.
Faces are NEVER stored without explicit consent records.
"""

import json
import os
import secrets
import time
from pathlib import Path

import numpy as np

from security.encryption import encrypt_json, decrypt_json

CONSENT_DIR = Path(__file__).parent.parent / ".face_consent"
EMBEDDINGS_DIR = CONSENT_DIR / "embeddings"


def _ensure_dirs():
    CONSENT_DIR.mkdir(exist_ok=True)
    EMBEDDINGS_DIR.mkdir(exist_ok=True)
    # Restrict permissions
    try:
        os.chmod(str(CONSENT_DIR), 0o700)
        os.chmod(str(EMBEDDINGS_DIR), 0o700)
    except OSError:
        pass


def create_consent(
    person_name: str,
    domain: str,
    role: str,
    consent_source: str,
    cameras: list[str] | None = None,
    expires_at: float | None = None,
    guardian_name: str | None = None,
    notes: str = "",
) -> dict:
    """Create a consent record for face recognition enrollment.

    Args:
        person_name: Name of the person being enrolled
        domain: "aba", "retail", "security", or "custom"
        role: Domain-specific role (e.g., "client", "therapist", "employee")
        consent_source: How consent was obtained (e.g., "signed_form", "hr_onboarding")
        cameras: List of camera IDs this consent applies to (None = all)
        expires_at: Unix timestamp when consent expires (None = no expiry)
        guardian_name: For minors — name of consenting guardian
        notes: Additional notes
    """
    _ensure_dirs()
    consent_id = secrets.token_hex(8)
    record = {
        "consent_id": consent_id,
        "person_name": person_name,
        "domain": domain,
        "role": role,
        "consent_source": consent_source,
        "cameras": cameras,
        "expires_at": expires_at,
        "guardian_name": guardian_name,
        "notes": notes,
        "created_at": time.time(),
        "revoked": False,
        "revoked_at": None,
        "enrolled": False,
        "embedding_count": 0,
    }

    path = CONSENT_DIR / f"{consent_id}.json"
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass

    return record


def get_consent(consent_id: str) -> dict | None:
    """Get a consent record by ID."""
    path = CONSENT_DIR / f"{consent_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def list_consents(domain: str | None = None, include_revoked: bool = False) -> list[dict]:
    """List all consent records, optionally filtered by domain."""
    _ensure_dirs()
    consents = []
    for f in CONSENT_DIR.glob("*.json"):
        with open(f) as fh:
            record = json.load(fh)
        if not include_revoked and record.get("revoked"):
            continue
        if domain and record.get("domain") != domain:
            continue
        # Check expiration
        if record.get("expires_at") and record["expires_at"] < time.time():
            record["expired"] = True
        else:
            record["expired"] = False
        consents.append(record)
    return consents


def revoke_consent(consent_id: str) -> bool:
    """Revoke consent and securely delete all face embeddings."""
    record = get_consent(consent_id)
    if not record:
        return False

    # Securely delete embeddings
    emb_path = EMBEDDINGS_DIR / f"{consent_id}.enc"
    if emb_path.exists():
        # Overwrite with random data before deletion
        size = emb_path.stat().st_size
        with open(emb_path, "wb") as f:
            f.write(os.urandom(size))
        emb_path.unlink()

    # Update consent record
    record["revoked"] = True
    record["revoked_at"] = time.time()
    record["enrolled"] = False
    record["embedding_count"] = 0

    path = CONSENT_DIR / f"{consent_id}.json"
    with open(path, "w") as f:
        json.dump(record, f, indent=2)

    return True


def save_embeddings(consent_id: str, embeddings: list[list[float]]) -> bool:
    """Save face embeddings (encrypted) for a consented person."""
    _ensure_dirs()
    record = get_consent(consent_id)
    if not record or record.get("revoked"):
        return False

    # Encrypt and save embeddings
    data = {"consent_id": consent_id, "embeddings": embeddings, "saved_at": time.time()}
    encrypted = encrypt_json(data)
    emb_path = EMBEDDINGS_DIR / f"{consent_id}.enc"
    emb_path.write_text(encrypted)
    try:
        os.chmod(str(emb_path), 0o600)
    except OSError:
        pass

    # Update consent record
    record["enrolled"] = True
    record["embedding_count"] = len(embeddings)
    path = CONSENT_DIR / f"{consent_id}.json"
    with open(path, "w") as f:
        json.dump(record, f, indent=2)

    return True


def load_embeddings(consent_id: str) -> list[list[float]] | None:
    """Load and decrypt face embeddings for a consented person."""
    emb_path = EMBEDDINGS_DIR / f"{consent_id}.enc"
    if not emb_path.exists():
        return None
    try:
        data = decrypt_json(emb_path.read_text())
        return data.get("embeddings", [])
    except Exception:
        return None


def load_all_enrolled() -> dict[str, dict]:
    """Load all enrolled (consented, non-revoked, non-expired) face data.

    Returns: {consent_id: {"name": str, "role": str, "domain": str, "embeddings": list}}
    """
    enrolled = {}
    for record in list_consents():
        if not record.get("enrolled") or record.get("expired"):
            continue
        embeddings = load_embeddings(record["consent_id"])
        if embeddings:
            enrolled[record["consent_id"]] = {
                "name": record["person_name"],
                "role": record["role"],
                "domain": record["domain"],
                "embeddings": embeddings,
            }
    return enrolled
