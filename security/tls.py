"""Generate self-signed TLS certificates for HTTPS."""

import subprocess
from pathlib import Path

CERTS_DIR = Path(__file__).parent.parent / ".certs"


def ensure_certs() -> tuple[str, str]:
    """Ensure TLS cert and key exist. Generate if missing. Returns (cert_path, key_path)."""
    CERTS_DIR.mkdir(exist_ok=True)
    cert_path = CERTS_DIR / "server.crt"
    key_path = CERTS_DIR / "server.key"

    if cert_path.exists() and key_path.exists():
        return str(cert_path), str(key_path)

    print("[tls] Generating self-signed TLS certificate...")
    try:
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-days", "365",
            "-nodes",
            "-subj", "/CN=aba-observer/O=ABA Observer/C=US",
        ], check=True, capture_output=True)
        print("[tls] Certificate generated successfully.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[tls] WARNING: Could not generate TLS cert (openssl not found).")
        print("[tls] Running without HTTPS. Use a reverse proxy (nginx/cloudflare) for TLS in production.")
        return "", ""

    return str(cert_path), str(key_path)
