"""AES-256-GCM encryption for PHI data at rest."""

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path

# Derive encryption key from a passphrase stored in env
# In production, use a KMS or hardware security module
_KEY_ENV = "ABA_ENCRYPTION_KEY"


def _get_key() -> bytes:
    """Get or generate the 256-bit encryption key."""
    key_file = Path(__file__).parent.parent / ".encryption_key"
    raw = os.environ.get(_KEY_ENV)

    if raw:
        # Derive 32-byte key from passphrase via SHA-256
        return hashlib.sha256(raw.encode()).digest()

    if key_file.exists():
        return base64.b64decode(key_file.read_text().strip())

    # First run: generate and save a key
    key = secrets.token_bytes(32)
    key_file.write_text(base64.b64encode(key).decode())
    # Restrict file permissions (best-effort on Windows)
    try:
        os.chmod(str(key_file), 0o600)
    except OSError:
        pass
    return key


def encrypt_data(plaintext: str) -> str:
    """Encrypt a string with AES-256-GCM. Returns base64-encoded ciphertext."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _get_key()
    nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Pack: nonce (12) + ciphertext (variable)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_data(encoded: str) -> str:
    """Decrypt AES-256-GCM encrypted data."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _get_key()
    raw = base64.b64decode(encoded)
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def encrypt_json(data: dict) -> str:
    """Encrypt a dict as JSON."""
    return encrypt_data(json.dumps(data))


def decrypt_json(encoded: str) -> dict:
    """Decrypt to a dict."""
    return json.loads(decrypt_data(encoded))


def secure_delete(path: Path):
    """Overwrite file with random data before unlinking (best-effort secure delete)."""
    if not path.exists():
        return
    size = path.stat().st_size
    with open(path, "wb") as f:
        f.write(secrets.token_bytes(size))
        f.flush()
        os.fsync(f.fileno())
    path.unlink()
