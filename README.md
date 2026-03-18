# The I — Intelligent Video Analytics

Self-hosted, privacy-first, multi-domain AI video analytics platform. Camera-agnostic with consent-based facial recognition.

## Domains

- **ABA Therapy** — Behavioral observation, ABC chains, frequency counts, pose analysis, PDF reports
- **Retail/Hospitality** — Traffic counting, dwell time, queues, POS integration, heatmaps
- **Security** — Fall detection, loitering, crowd density, access control, vehicle detection
- **Custom** — User-defined rules and detection targets

## Quick Start

```bash
# Clone
git clone https://github.com/AuthSoftware-development/aba-observer.git
cd aba-observer

# Install dependencies
pip install -r requirements.txt

# Configure (copy and edit)
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY

# Start server (HTTPS on port 3017)
python server.py

# Open https://localhost:3017
# First visit: create admin account
```

### Docker

```bash
# Build and run
docker compose up -d

# With API key
GOOGLE_API_KEY=your-key docker compose up -d
```

## CLI Usage

```bash
# Analyze a video file (no auth required)
python main.py analyze --video session.mp4

# Specify provider
python main.py analyze --video session.mp4 --provider gemini

# With client config
python main.py analyze --video session.mp4 --config configs/example_client.json
```

## API

62 endpoints across auth, AI analysis, CV detection, face recognition, retail, security, search, and platform management.

Full API docs available at `https://localhost:3017/docs` (Swagger UI) after starting the server.

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/auth/setup` | First-time admin creation |
| `POST /api/auth/login` | PIN login → session token |
| `POST /api/analyze` | Upload video for AI behavioral analysis |
| `POST /api/cv/analyze` | Person detection + tracking (CPU-only) |
| `POST /api/cv/recognize` | Face recognition (consent-based) |
| `POST /api/retail/analyze` | Retail metrics (traffic, dwell, heatmap) |
| `POST /api/security/analyze` | Security events (falls, loitering, crowds) |
| `POST /api/search/natural` | Natural language event search |
| `GET /api/system/status` | Platform health dashboard |

## Architecture

```
server.py              — FastAPI application (port 3017, HTTPS)
routes/                — API route modules
cv/                    — Computer vision pipeline
  detector.py          — Person detection (MobileNet-SSD, CPU-only)
  tracker.py           — Centroid-based multi-object tracking
  face.py              — Face detection + recognition (consent-based)
  pose.py              — Movement/stereotypy analysis
  safety.py            — Fall, loitering, crowd detection
  vehicle.py           — Vehicle detection + counting
domains/
  aba/                 — ABA therapy analytics
  retail/              — Retail/hospitality analytics
  security/            — Security monitoring + alerts
search/                — Full-text + face search engine
store/                 — Consent + data management
security/              — Auth, encryption, audit, compliance
notifications/         — Alert delivery (log, webhook, email)
ingest/                — RTSP camera + ONVIF discovery
```

## Security

- TLS (auto-generated self-signed cert)
- PIN-based auth with HMAC-signed session tokens
- AES-256-GCM encryption at rest for all analysis results
- Role-based access (admin, bcba, rbt)
- Append-only JSONL audit logging
- Secure video deletion (overwrite before unlink)
- API key management for third-party integrations
- Compliance modes: HIPAA (default), BIPA, CCPA/CPRA, GDPR

## CV Models

All models run on CPU — no GPU required.

| Model | Size | Purpose |
|-------|------|---------|
| MobileNet-SSD v2 | 23 MB | Person + vehicle detection |
| res10 SSD | 11 MB | Face detection |
| OpenFace nn4.small2 | 31 MB | Face embeddings (128-d) |

Models auto-download on first server start.

## Requirements

- Python 3.11+
- ~65 MB disk for CV models
- No GPU required (all CPU inference)
- Optional: GOOGLE_API_KEY for Gemini AI provider

## License

Proprietary — AuthSoftware Development
