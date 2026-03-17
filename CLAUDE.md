# The I — Intelligent Video Analytics

## Overview
Multi-domain AI video analytics platform with privacy-first architecture.
Self-hosted, camera-agnostic, consent-based facial recognition.
Domains: ABA therapy, retail/hospitality, security, custom.
HIPAA-compliant: encrypted storage, auth, audit logging, TLS.

## Tech Stack
- **Language:** Python 3.11+
- **Web:** FastAPI + Uvicorn (port 3017, HTTPS)
- **Frontend:** Vanilla HTML/JS + Tailwind CDN
- **AI Providers:** Google Gemini (cloud), Qwen2.5-Omni (local/HIPAA-safe)
- **CV Pipeline:** OpenCV DNN + MobileNet-SSD (CPU-only person detection)
- **Tracking:** Centroid-based multi-object tracker (scipy)
- **Encryption:** AES-256-GCM (cryptography library)
- **Auth:** HMAC-signed tokens with PIN login
- **TLS:** Self-signed cert (auto-generated)

## Dev Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Start server (HTTPS on port 3017)
GOOGLE_API_KEY=<key> python server.py

# CLI usage (no auth required)
python main.py analyze --video session.mp4
```

## Architecture
```
server.py              — FastAPI server (HTTPS, port 3017)
main.py                — CLI entry point (no auth)
static/index.html      — Web UI (login, upload, camera, data, audit)
providers/
  gemini.py            — Google Gemini API (cloud, NO BAA)
  qwen.py              — Qwen2.5-Omni (local, HIPAA-safe)
prompts/aba_system.py  — ABA observation prompt + schema
configs/               — Client behavior target configs
cv/
  detector.py          — MobileNet-SSD person detection (CPU-only)
  tracker.py           — Centroid-based multi-object tracking
  zones.py             — Polygon ROI zone management
  pipeline.py          — CV processing pipeline (ties detection+tracking)
  models/              — Model files (not committed, ~23MB)
ingest/
  rtsp.py              — RTSP camera ingest with auto-reconnect
security/
  auth.py              — PIN auth + HMAC tokens + session timeout + reset
  encryption.py        — AES-256-GCM encrypt/decrypt for PHI at rest
  audit.py             — Append-only JSONL audit logging
  tls.py               — Self-signed TLS cert generation
docs/
  SYSTEM_SPEC.md       — Full platform spec (10-phase roadmap)
```

## Security Layers (HIPAA)
1. **TLS** — HTTPS with auto-generated self-signed cert
2. **Authentication** — PIN-based login, HMAC-signed session tokens
3. **Session timeout** — 15-minute inactivity auto-logout
4. **Role-based access** — admin, bcba, rbt roles
5. **Encrypted storage** — AES-256-GCM for all analysis results (.enc files)
6. **Secure delete** — Videos overwritten with random data before unlinking
7. **Audit logging** — Append-only JSONL logs of all PHI access
8. **Security headers** — HSTS, X-Frame-Options, no-cache
9. **CORS locked** — Same-origin only
10. **HIPAA warnings** — UI warns when using cloud (non-BAA) providers

## Sensitive Files (never commit)
- `.encryption_key` — AES-256 key
- `.jwt_secret` — Token signing secret
- `.users.json` — User credentials (hashed PINs)
- `.certs/` — TLS certificates
- `audit_logs/` — PHI access audit trail
- `output/` — Encrypted analysis results
