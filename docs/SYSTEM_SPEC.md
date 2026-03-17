# Observer Platform — System Specification

> Multi-domain AI video analytics platform with privacy-first architecture.
> Self-hosted, camera-agnostic, consent-based facial recognition.

**Version:** 0.5.0 (spec)
**Status:** ABA domain MVP complete. Platform architecture in design.

---

## 1. Vision

A single self-hosted platform that processes video feeds from any camera system — consumer (Wyze, Eufy, Nest) or enterprise (Axis, Hikvision, Dahua via ONVIF/RTSP) — and produces domain-specific analytics. No video leaves the customer's network unless they explicitly choose a cloud AI provider.

**Domains:**
- **ABA Therapy** — Behavioral observation, ABC chains, frequency counts, session analytics
- **Retail/Hospitality** — Traffic counting, dwell time, queue analytics, peak hours
- **Security** — Motion detection, anomaly alerts, zone monitoring
- **Custom** — User-defined rules and detection targets

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    OBSERVER PLATFORM                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ Video Ingest │  │ CV Pipeline  │  │ AI Analysis     │ │
│  │             │  │             │  │                 │ │
│  │ • RTSP      │→ │ • Person    │→ │ • Gemini (cloud)│ │
│  │ • ONVIF     │  │   Detection │  │ • Qwen (local)  │ │
│  │ • File      │  │ • Tracking  │  │ • Ollama (local)│ │
│  │ • Webcam    │  │ • Counting  │  │ • OpenAI (cloud)│ │
│  │ • Consumer  │  │ • Face ID*  │  │                 │ │
│  │   bridges   │  │ • Zones     │  │ Domain prompts: │ │
│  │   (Wyze,    │  │ • Motion    │  │ • ABA behavioral│ │
│  │    Eufy,    │  │             │  │ • Retail traffic│ │
│  │    Nest)    │  │ *consent-   │  │ • Security      │ │
│  │             │  │  based only │  │ • Custom        │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
│         │                │                │             │
│         ▼                ▼                ▼             │
│  ┌─────────────────────────────────────────────────────┐│
│  │                   Event Store                       ││
│  │  • AES-256-GCM encrypted at rest                   ││
│  │  • Append-only audit log                           ││
│  │  • Time-series metrics (Redis/SQLite)              ││
│  │  • Retention policies per domain                   ││
│  └─────────────────────────────────────────────────────┘│
│         │                                               │
│         ▼                                               │
│  ┌─────────────────────────────────────────────────────┐│
│  │                   Presentation                      ││
│  │  • Web dashboard (per-domain views)                ││
│  │  • REST API                                        ││
│  │  • Alerts (email, webhook, push)                   ││
│  │  • Reports (PDF export)                            ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
├─────────────────────────────────────────────────────────┤
│  Auth: PIN/password + roles │ TLS │ HIPAA │ Audit logs  │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Core Modules

### 3.1 Video Ingest (`ingest/`)

Accepts video from any source and normalizes to frames for processing.

| Source Type | Protocol | Implementation |
|------------|----------|---------------|
| Enterprise IP cameras | ONVIF discovery + RTSP streaming | `python-onvif-zeep` for discovery, OpenCV `VideoCapture` for RTSP |
| Consumer: Wyze | docker-wyze-bridge → RTSP | Bridge container exposes RTSP endpoints |
| Consumer: Eufy | `eufy-security-client` → RTSP (supported models) | Node.js bridge, select models only |
| Consumer: Nest | Device Access API → WebRTC/RTSP | Token refresh every 5 min, `nest-rtsp` bridge |
| Consumer: Ring | `ring-mqtt` → RTSP | Unofficial API, fragile — not recommended for production |
| File upload | HTTP multipart | Existing `/api/analyze` endpoint |
| Webcam/device | USB/built-in camera | OpenCV `VideoCapture(0)` |
| RTMP stream | RTMP ingest | FFmpeg → frame extraction |

**Camera management:**
- Add/remove cameras via API and dashboard
- Per-camera config: resolution, FPS target, recording schedule
- Health monitoring: connection status, frame drops, reconnect logic
- Multi-camera support: process N cameras concurrently

### 3.2 CV Pipeline (`cv/`)

Local computer vision processing — runs entirely on-device, no cloud dependency.

| Capability | Model | Hardware Requirement | Use Case |
|-----------|-------|---------------------|----------|
| Person detection | MobileNet-SSD v2 | CPU (any) | Count people in frame |
| Person tracking | Centroid / DeepSORT | CPU (any) | Track individuals across frames |
| Face detection | MediaPipe / RetinaFace | CPU (any) | Locate faces for recognition |
| Face recognition | ArcFace / FaceNet | CPU (GPU preferred) | Identify consented individuals |
| Pose estimation | MediaPipe Pose | CPU (any) | Body position, movement patterns |
| Zone detection | Polygon ROI | CPU (any) | Define areas of interest |
| Motion detection | Frame differencing / MOG2 | CPU (any) | Detect activity changes |
| License plate recognition | PaddleOCR / OpenALPR | CPU (any) | Parking lots, drive-throughs |
| Vehicle detection | YOLOv8-nano | CPU (any) | Count vehicles, parking occupancy |
| Heat mapping | Accumulative tracking overlay | CPU (any) | Visual foot traffic patterns |
| Crowd density estimation | CSRNet / density regression | CPU (GPU preferred) | Large venue occupancy |
| Slip/fall detection | Pose + motion analysis | CPU (any) | Safety, liability prevention |
| Smoke/fire detection | Custom CNN / YOLOv8 | CPU (GPU preferred) | Faster than traditional sensors |
| Weapons detection | Custom object detection | GPU preferred | School/workplace safety |
| Demographics estimation | Age/gender CNN | CPU (any) | Shopper segmentation (anonymized) |

**Face recognition consent model:**
- Faces are NEVER stored or processed without explicit consent
- Consent enrollment: authorized user captures reference photos + signs consent form
- Consent is stored per-person with expiration date and scope (which cameras, which domains)
- Non-consented faces are detected but NOT identified — rendered as "Person A", "Person B"
- ABA domain: therapist + client faces enrolled with guardian consent (minors)
- Retail domain: employee faces enrolled via HR onboarding; customers are NEVER enrolled
- All face embeddings encrypted at rest with separate key from general data
- Consent can be revoked at any time — embeddings are securely deleted

### 3.3 AI Analysis (`analysis/`)

Multimodal AI models analyze video context for domain-specific insights.

**Provider architecture (existing, extended):**
```python
class AnalysisProvider(Protocol):
    def is_available(self) -> bool: ...
    async def analyze(self, video_path: str, prompt: str, schema: dict) -> dict: ...
```

| Provider | Type | HIPAA-Safe | Best For |
|---------|------|-----------|---------|
| Qwen2.5-Omni | Local | Yes | Full video understanding, ABA |
| Ollama (LLaVA, etc.) | Local | Yes | Lightweight local analysis |
| Gemini | Cloud | No (no BAA) | Best quality, dev/testing |
| OpenAI (GPT-4V) | Cloud | Yes (BAA available) | Production cloud option |
| Claude | Cloud | Yes (BAA available) | Production cloud option |

### 3.4 Domain Modules (`domains/`)

Each domain defines: prompts, schemas, dashboards, alerts, and reports.

#### 3.4.1 ABA Therapy Domain (`domains/aba/`)

**Current (v0.4.0 — working):**
- ABC chain detection (antecedent → behavior → consequence)
- Behavior frequency counting with timestamps
- Prompt level tracking (independent → full physical)
- Session summary (setting, people, duration, notes)
- Per-client behavior target configs
- Behavior library with fuzzy matching

**Planned additions:**
- **Client identification** — Face recognition (with guardian consent) to auto-tag which client is in session
- **Therapist tracking** — Identify therapist, track proximity to client
- **Attention metrics** — Gaze direction estimation, on-task vs off-task time
- **Movement patterns** — Track stereotypical movements, self-stimulatory behaviors via pose estimation
- **Session compliance** — Verify required participants present, session duration met
- **Inter-observer agreement** — Compare AI observations with human-coded data
- **Progress tracking** — Trend graphs across sessions per behavior target
- **Report generation** — PDF session reports for BCBAs, formatted for insurance

#### 3.4.2 Retail/Hospitality Domain (`domains/retail/`)

**Core Analytics:**
- **Traffic counting** — Entries/exits per hour, daily/weekly trends
- **Dwell time** — How long customers spend in defined zones
- **Queue analytics** — Queue length, wait time estimation, service time
- **Peak hours** — Heatmap of busiest times
- **Staff tracking** — Employee presence in zones (consented faces only)
- **Conversion rate** — Traffic vs POS transactions (requires POS integration)
- **Zone heatmaps** — Visual foot traffic overlay on floor plan
- **Occupancy monitoring** — Real-time count vs capacity limit
- **Customer journey/path analysis** — Track shopper path across multiple cameras

**POS Integration:**
- **Transaction matching** — Correlate POS events with video timestamps
- **Exception-based reporting** — Auto-flag suspicious transactions (voids, no-sales, sweethearting)
- **Shrinkage analysis** — Match inventory loss patterns with video evidence
- Supported POS systems: Square, Toast, Clover, generic CSV/API

**Drive-Through / Parking:**
- **License plate recognition** — Track vehicles at drive-throughs, parking lots
- **Vehicle counting** — Parking lot occupancy, drive-through throughput
- **Service time measurement** — Order-to-pickup timing at drive-through windows

**Demographics (anonymized, no face storage):**
- **Age/gender estimation** — Shopper segmentation for marketing insights
- **Group detection** — Families, couples, solo shoppers
- Note: demographics are estimated per-frame, never stored with identity

#### 3.4.3 Security Domain (`domains/security/`)

**Detection & Monitoring:**
- **Motion detection** — Activity in defined zones during off-hours
- **Anomaly alerts** — Unusual patterns (loitering, running, crowds forming)
- **Person counting** — Occupancy monitoring
- **Zone violations** — Unauthorized access to restricted areas
- **Event timeline** — Searchable log of all detected events with video clips
- **Slip & fall detection** — Automatic alert on detected falls (liability/safety)
- **Smoke/fire detection** — Visual detection faster than traditional sensors
- **Weapons detection** — Alert on detected weapons (schools, workplaces)
- **Crowd density** — Alert when density exceeds thresholds

**Access Control Integration:**
- **Door/badge events** — Correlate access control events with video
- **Tailgating detection** — Multiple people entering on single badge swipe
- **Supported systems:** HID, Lenel, Brivo, generic Wiegand via API/webhook

**Vehicle & Perimeter:**
- **License plate recognition** — Entry/exit logging, allow/deny lists
- **Vehicle counting** — Parking lot occupancy tracking
- **Perimeter monitoring** — Fence line and boundary detection

**AI-Powered Search:**
- **Natural language search** — "Show me everyone near the back door after 10pm"
- **Face search** — Find appearances of a consented person across all cameras
- **Reverse image search** — Upload a photo to find matches in footage
- **Object search** — Search by clothing, carried items, vehicle type

#### 3.4.4 Custom Domain (`domains/custom/`)

- User-defined detection rules (YAML/JSON config)
- Custom prompts for AI analysis
- Webhook integrations for events
- Flexible schema for domain-specific data

---

## 4. Data Architecture

### 4.1 Event Store

All observations are stored as typed events:

```json
{
  "event_id": "uuid",
  "camera_id": "lobby-cam-1",
  "domain": "retail",
  "event_type": "person_entered",
  "timestamp": "2026-03-17T14:30:00Z",
  "data": {
    "zone": "entrance",
    "person_id": "anonymous-track-42",
    "direction": "in"
  },
  "metadata": {
    "model": "mobilenet-ssd-v2",
    "confidence": 0.94
  }
}
```

### 4.2 Storage Tiers

| Tier | Technology | Purpose | Retention |
|------|-----------|---------|-----------|
| Hot | SQLite / Redis | Real-time metrics, active sessions | 24-48 hours |
| Warm | SQLite | Historical analytics, searchable events | 30-90 days |
| Cold | Encrypted files (.enc) | Archived sessions, compliance records | Per policy (HIPAA: 6 years) |

### 4.3 Metrics Pipeline

```
Camera Frame → CV Pipeline → Event → Time-Series DB → Dashboard
                                   → Alert Engine → Notifications
                                   → AI Analysis → Domain insights
```

---

## 5. Security & Compliance

### 5.1 Existing (v0.4.0)

- [x] TLS (self-signed, auto-generated)
- [x] PIN-based auth with HMAC-signed tokens
- [x] PIN reset (self-service + admin)
- [x] Session timeout (15 min)
- [x] Role-based access (admin, bcba, rbt)
- [x] AES-256-GCM encryption at rest
- [x] Secure video deletion (overwrite before unlink)
- [x] Append-only audit logging
- [x] Security headers (HSTS, X-Frame-Options, no-cache)
- [x] CORS locked to same-origin
- [x] HIPAA warnings for cloud providers

### 5.2 Planned

- [ ] Face embedding encryption (separate key)
- [ ] Consent management system (enrollment, expiration, revocation)
- [ ] Data retention policies (auto-purge per domain rules)
- [ ] Multi-tenant isolation (separate encryption keys per organization)
- [ ] BIPA compliance mode (disable face recognition for Illinois deployments)
- [ ] CCPA/CPRA compliance (opt-out for biometric data sale/sharing)
- [ ] GDPR mode (consent-first, right to erasure, data portability)
- [ ] Audit log export (for compliance audits)
- [ ] BAA tracking (which cloud providers have BAAs)
- [ ] Video redaction tools (blur faces, mask areas)
- [ ] Two-factor authentication option (PIN + TOTP)
- [ ] API key management for third-party integrations
- [ ] Rate limiting per API key/user

### 5.3 Facial Recognition Consent Framework

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│ Consent Form │ ──→ │ Enrollment      │ ──→ │ Face DB      │
│ (signed)     │     │ (capture photos)│     │ (encrypted)  │
└──────────────┘     └─────────────────┘     └──────────────┘
                                                    │
                                              ┌─────▼─────┐
                                              │ Matching   │
                                              │ Engine     │
                                              └─────┬─────┘
                                                    │
                          ┌─────────────────────────┼────────────────┐
                          │                         │                │
                    ┌─────▼─────┐           ┌──────▼──────┐   ┌────▼────┐
                    │ Consented  │           │ Unknown     │   │ Revoked │
                    │ → Name ID  │           │ → "Person X"│   │ → Delete│
                    └───────────┘           └─────────────┘   └─────────┘
```

**Per-domain consent rules:**

| Domain | Who Gets Enrolled | Consent Source | Auto-Expire |
|--------|------------------|----------------|-------------|
| ABA | Client (minor → guardian consent), therapist | Signed consent form, stored in system | End of treatment or annual renewal |
| Retail | Employees only | HR onboarding, signed consent | Employment termination |
| Security | Authorized personnel | Admin enrollment | Annual renewal |
| Custom | Configurable | Configurable | Configurable |

---

## 6. Camera Integration Tiers

### Tier 1 — Full Support (ship with)
- **ONVIF/RTSP** — Any enterprise IP camera (Axis, Hikvision, Dahua, Bosch, Hanwha)
- **File upload** — Any video file (MP4, WebM, AVI, MOV)
- **Webcam** — USB/built-in cameras
- **Wyze** — Via docker-wyze-bridge (most reliable consumer bridge)

### Tier 2 — Supported (community bridges)
- **Eufy** — Via eufy-security-client (RTSP on supported models)
- **Nest** — Via Device Access API (5-min token refresh)
- **Generic RTMP** — Any camera that pushes RTMP

### Tier 3 — Experimental (fragile, not recommended)
- **Ring** — Via ring-mqtt (unofficial API, Amazon may break anytime)
- **Other proprietary** — Case-by-case via FFmpeg or custom bridges

### Not Supported
- **Blink (Amazon)** — No official API, no RTSP, no live streaming capability. Battery-powered cameras only record on motion events. `blinkpy` library can download stored clips but cannot provide continuous video feeds. No RTSP bridge exists (unlike Ring). Fundamentally incompatible with real-time observation.

---

## 7. Deployment Models

### 7.1 Single Device (Current)
- All-in-one: ingest + CV + AI + dashboard on one machine
- Best for: single clinic, small shop, home use
- Hardware: any modern PC/laptop, or Raspberry Pi 5 (limited CV)

### 7.2 Edge + Hub
- Edge devices per camera (Jetson Nano/Orin, Intel NUC) run CV pipeline
- Hub server aggregates events, runs AI analysis, serves dashboard
- Best for: multi-location retail, large clinic

### 7.3 On-Premise Server
- Dedicated server with GPU for all processing
- NVR-style deployment alongside existing camera infrastructure
- Best for: stores with existing CCTV systems (Target, Costco pattern)

### 7.4 Hybrid Cloud (Planned)
- Local CV processing (privacy-first — video never leaves network)
- Cloud sync for: aggregated metrics, multi-location dashboards, alerts, reports
- Cloud storage option for non-PHI analytics data only
- Best for: multi-location retail chains needing centralized reporting

### 7.5 Mobile App (Planned)
- iOS + Android (React Native or Flutter)
- Live camera feeds, alerts, dashboard summaries
- Push notifications for security/anomaly events
- Role-based access (manager vs staff vs security)
- Offline-capable with sync on reconnect

---

## 8. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.11+ | CV/ML ecosystem, existing codebase |
| Web framework | FastAPI + Uvicorn | Async, WebSocket support for live feeds |
| Frontend | React + Tailwind | Dashboard with real-time updates, charts |
| Mobile | React Native or Flutter | Cross-platform iOS + Android |
| CV models | OpenCV + MediaPipe + ONNX Runtime | Runs on CPU, no CUDA required |
| Face recognition | InsightFace (ArcFace) via ONNX | Best accuracy, CPU-capable via ONNX |
| Object detection | MobileNet-SSD v2 / YOLOv8-nano | Lightweight, 30+ FPS on CPU |
| Tracking | DeepSORT or ByteTrack | Multi-object tracking across frames |
| LPR | PaddleOCR / OpenALPR | License plate recognition |
| Pose estimation | MediaPipe Pose / MoveNet | Body position for fall/behavior detection |
| Time-series | SQLite (small) / TimescaleDB (large) | Metrics storage |
| Search | SQLite FTS5 / Meilisearch | Natural language event search |
| Encryption | AES-256-GCM (cryptography lib) | PHI at rest |
| Video streaming | FFmpeg + OpenCV | Universal codec support |
| Camera discovery | python-onvif-zeep | ONVIF device management |
| POS integration | REST webhooks + adapters | Square, Toast, Clover |
| Access control | Webhook + Wiegand adapters | HID, Lenel, Brivo |
| Reports | WeasyPrint / ReportLab | PDF generation |
| Notifications | SMTP + Twilio + Firebase | Email, SMS, push |
| Containerization | Docker + Docker Compose | Consistent deployment |
| API docs | FastAPI auto-gen (OpenAPI/Swagger) | Developer SDK foundation |

---

## 9. API Surface

### Existing Endpoints (v0.4.0)
- `POST /api/auth/setup` — First-time admin creation
- `POST /api/auth/login` — PIN login
- `POST /api/auth/refresh` — Token refresh
- `POST /api/auth/create-user` — Admin: create user
- `POST /api/auth/reset-pin` — Reset PIN (self or admin)
- `GET /api/providers` — List AI providers
- `GET /api/configs` — List client configs
- `GET /api/configs/{name}` — Get config
- `POST /api/configs` — Save config
- `POST /api/analyze` — Upload + analyze video
- `POST /api/analyze-recording` — Analyze camera recording
- `GET /api/history` — List analysis history
- `GET /api/history/{name}` — Get analysis detail
- `DELETE /api/history/{name}` — Delete analysis
- `GET /api/audit` — View audit log
- `GET /api/behavior-library` — Get behavior library
- `POST /api/configs/{name}/behaviors` — Add behavior to config
- `DELETE /api/configs/{name}/behaviors/{behavior}` — Remove behavior
- `POST /api/configs/{name}/fuzzy-match` — Fuzzy match behavior

### Planned Endpoints

**Camera Management:**
- `GET/POST/PUT/DELETE /api/cameras` — Camera CRUD
- `GET /api/cameras/{id}/stream` — Live stream (WebSocket/SSE)
- `GET /api/cameras/{id}/snapshot` — Current frame capture
- `POST /api/cameras/{id}/zones` — Define ROI zones (polygon coordinates)
- `GET /api/cameras/discover` — ONVIF auto-discovery on network

**Consent & Face Recognition:**
- `GET/POST/DELETE /api/consent` — Consent record management
- `POST /api/consent/{id}/enroll` — Face enrollment (capture + embed)
- `DELETE /api/consent/{id}/revoke` — Revoke consent + secure-delete embeddings
- `GET /api/consent/{id}/status` — Check consent validity/expiration

**Analytics & Metrics:**
- `GET /api/metrics/{domain}` — Domain metrics (time-series, filterable)
- `GET /api/metrics/{domain}/realtime` — Live metrics (WebSocket)
- `GET /api/metrics/{domain}/heatmap` — Heat map data for floor plan overlay
- `GET /api/dashboard/{domain}` — Dashboard summary data

**Search:**
- `POST /api/search/natural` — Natural language video search
- `POST /api/search/face` — Face search across cameras (consented only)
- `POST /api/search/image` — Reverse image search
- `POST /api/search/events` — Structured event search with filters

**POS Integration:**
- `POST /api/pos/webhook` — Receive POS transaction events
- `GET /api/pos/exceptions` — Exception-based reporting (flagged transactions)
- `GET /api/pos/match/{transaction_id}` — Get video clip for transaction

**Access Control:**
- `POST /api/access-control/webhook` — Receive door/badge events
- `GET /api/access-control/events` — Access events with linked video

**Alerts & Notifications:**
- `GET/POST/PUT/DELETE /api/alerts` — Alert rule management
- `GET /api/alerts/history` — Alert history log
- `POST /api/alerts/test` — Test alert delivery

**Reports:**
- `GET /api/reports/{domain}` — Generate domain report (PDF)
- `GET /api/reports/{domain}/schedule` — Scheduled report config
- `POST /api/reports/{domain}/export` — Export data (CSV, JSON)

**Platform:**
- `GET /api/system/status` — System health, camera status, resource usage
- `GET /api/system/config` — Platform configuration
- `POST /api/api-keys` — Generate API keys for third-party access
- `GET /api/sdk/docs` — API documentation (OpenAPI/Swagger)

---

## 10. Roadmap

### Phase 1 — ABA Observer MVP (COMPLETE)
- [x] Video upload + AI analysis (Gemini, Qwen)
- [x] ABC chain detection, frequency counting
- [x] HIPAA security stack (auth, encryption, audit, TLS)
- [x] Web UI (login, upload, camera, history, audit)
- [x] Per-client behavior configs + behavior library
- [x] PIN reset

### Phase 2 — CV Pipeline + Person Detection
- [ ] MobileNet-SSD person detection (CPU-only, no GPU required)
- [ ] Centroid/DeepSORT tracking (persist IDs across frames)
- [ ] Zone definition (polygon ROI via dashboard)
- [ ] Person count overlay on video/dashboard
- [ ] RTSP camera ingest (enterprise cameras)

### Phase 3 — Face Recognition (Consent-Based)
- [ ] Consent management system (enroll, expire, revoke)
- [ ] Face detection (MediaPipe/RetinaFace)
- [ ] Face embedding generation + encrypted storage (ArcFace/ONNX)
- [ ] Face matching engine (consented → name, unknown → "Person X")
- [ ] ABA: auto-tag client/therapist in sessions
- [ ] Retail: employee identification

### Phase 4 — Retail Domain
- [ ] Traffic counting (entries/exits per hour, daily/weekly trends)
- [ ] Dwell time per zone
- [ ] Queue length + wait time estimation
- [ ] Peak hours heatmap
- [ ] Staff zone presence (consented faces)
- [ ] Zone heat mapping (visual foot traffic overlay)
- [ ] Customer journey/path analysis across cameras
- [ ] Occupancy monitoring (real-time vs capacity)
- [ ] Retail dashboard
- [ ] POS integration (Square, Toast, Clover, generic API)
- [ ] Exception-based reporting (suspicious transactions)
- [ ] Demographics estimation (anonymized age/gender)

### Phase 5 — Advanced ABA Features
- [ ] Pose estimation for movement/stereotypy detection
- [ ] Attention metrics (gaze direction estimation)
- [ ] Progress tracking across sessions (trend graphs)
- [ ] PDF report generation for BCBAs (insurance-formatted)
- [ ] Inter-observer agreement scoring
- [ ] Session compliance verification (participants, duration)

### Phase 6 — Security Domain + LPR
- [ ] Slip & fall detection (pose + motion analysis)
- [ ] Smoke/fire detection (visual, faster than sensors)
- [ ] Weapons detection
- [ ] License plate recognition (drive-throughs, parking)
- [ ] Vehicle counting and parking occupancy
- [ ] Access control integration (HID, Lenel, Brivo, Wiegand)
- [ ] Tailgating detection (multi-entry on single badge)
- [ ] Perimeter monitoring

### Phase 7 — AI Search + Intelligence
- [ ] Natural language video search ("show me everyone near register at 3pm")
- [ ] Face search across cameras (consented persons only)
- [ ] Reverse image search (upload photo → find in footage)
- [ ] Object/clothing search
- [ ] Automated scorecards and workflow triggers
- [ ] AI talk-down / live deterrence messaging

### Phase 8 — Platform Maturity
- [ ] Docker Compose deployment
- [ ] Multi-camera concurrent processing
- [ ] ONVIF camera auto-discovery
- [ ] Consumer camera bridges (Wyze, Eufy, Nest)
- [ ] Alert engine (email, webhook, SMS, push)
- [ ] Multi-tenant support (separate encryption keys per org)
- [ ] Edge + Hub deployment model
- [ ] Hybrid cloud sync (metrics only, video stays local)
- [ ] Two-way audio with real-time translation

### Phase 9 — Mobile + Developer Platform
- [ ] Mobile app (iOS + Android)
- [ ] Push notifications for alerts
- [ ] Live camera feeds on mobile
- [ ] API key management + developer SDK
- [ ] OpenAPI/Swagger documentation
- [ ] Webhook framework for third-party integrations
- [ ] White-label / OEM option
- [ ] Environmental sensor integration (temperature, humidity, air quality)

### Phase 10 — Enterprise + Compliance
- [ ] BIPA compliance mode (Illinois biometric consent)
- [ ] CCPA/CPRA compliance (California privacy)
- [ ] GDPR mode (EU data protection)
- [ ] SOC 2 Type II audit trail
- [ ] Digital evidence management (chain of custody)
- [ ] Multi-location centralized management
- [ ] Role hierarchy with location-scoped permissions
- [ ] Scheduled reporting (daily/weekly/monthly PDF delivery)

---

## 11. File Structure (Target)

```
observer/
├── server.py                  — FastAPI application
├── main.py                    — CLI entry point
├── ingest/
│   ├── rtsp.py               — RTSP/ONVIF camera ingest
│   ├── file.py               — File upload handler
│   ├── webcam.py             — Local camera capture
│   ├── manager.py            — Camera lifecycle management
│   └── bridges/
│       ├── wyze.py           — Wyze bridge integration
│       ├── eufy.py           — Eufy bridge integration
│       └── nest.py           — Nest API integration
├── cv/
│   ├── detector.py           — Person detection (MobileNet-SSD)
│   ├── tracker.py            — Multi-object tracking (DeepSORT)
│   ├── face.py               — Face detection + recognition
│   ├── pose.py               — Pose estimation
│   ├── zones.py              — ROI zone management
│   ├── lpr.py                — License plate recognition
│   ├── vehicle.py            — Vehicle detection + counting
│   ├── heatmap.py            — Accumulative heat map generation
│   ├── safety.py             — Slip/fall, smoke/fire, weapons detection
│   ├── demographics.py       — Anonymized age/gender estimation
│   ├── crowd.py              — Crowd density estimation
│   └── models/               — ONNX model files
├── analysis/
│   ├── providers/
│   │   ├── gemini.py         — Google Gemini
│   │   ├── qwen.py           — Local Qwen
│   │   ├── ollama.py         — Local Ollama
│   │   ├── openai.py         — OpenAI API
│   │   └── claude.py         — Anthropic Claude
│   └── prompts/
│       ├── aba.py            — ABA observation prompt
│       ├── retail.py         — Retail analytics prompt
│       └── security.py       — Security monitoring prompt
├── domains/
│   ├── aba/
│   │   ├── config.py         — ABA-specific settings
│   │   ├── dashboard.py      — ABA dashboard data
│   │   ├── reports.py        — PDF report generation
│   │   └── behaviors.py      — Behavior library + fuzzy match
│   ├── retail/
│   │   ├── config.py         — Retail settings
│   │   ├── dashboard.py      — Retail dashboard data
│   │   ├── metrics.py        — Traffic, dwell, queue calcs
│   │   ├── pos.py            — POS integration (Square, Toast, etc.)
│   │   ├── exceptions.py     — Exception-based transaction reporting
│   │   └── journey.py        — Customer path analysis
│   ├── security/
│   │   ├── config.py         — Security settings
│   │   ├── dashboard.py      — Security dashboard data
│   │   ├── alerts.py         — Alert rules engine
│   │   ├── access_control.py — Door/badge event integration
│   │   └── search.py         — Natural language + face + image search
│   └── custom/
│       └── config.py         — User-defined rules
├── store/
│   ├── events.py             — Event storage + retrieval
│   ├── metrics.py            — Time-series metrics
│   ├── consent.py            — Consent + face embedding store
│   ├── retention.py          — Data retention policies
│   └── cloud_sync.py         — Hybrid cloud metrics sync
├── security/
│   ├── auth.py               — PIN auth + tokens + reset
│   ├── encryption.py         — AES-256-GCM
│   ├── audit.py              — Audit logging
│   ├── tls.py                — TLS cert generation
│   ├── api_keys.py           — API key management
│   └── compliance.py         — HIPAA/BIPA/CCPA/GDPR mode config
├── notifications/
│   ├── engine.py             — Alert delivery engine
│   ├── email.py              — Email notifications
│   ├── webhook.py            — Webhook delivery
│   ├── sms.py                — SMS notifications
│   └── push.py               — Mobile push notifications
├── static/                    — Web dashboard
├── mobile/                    — Mobile app (React Native / Flutter)
├── configs/                   — Per-client/per-store configs
├── docs/
│   └── SYSTEM_SPEC.md        — This file
├── CHANGELOG.md               — Version history
└── docker-compose.yml         — Container deployment
```

---

## 12. Competitive Position

| Feature | Observer | Verkada | Spot AI | RetailNext | March Networks | Genetec | Frigate |
|---------|----------|---------|---------|------------|----------------|---------|---------|
| Self-hosted | Yes | No | Hybrid | No | Hybrid | Yes | Yes |
| ABA therapy analytics | Yes | No | No | No | No | No | No |
| Retail analytics | Yes | Yes | Yes | Yes | Yes | No | No |
| POS integration | Yes | Yes | No | Yes | Yes | No | No |
| Consent-based face ID | Yes | Yes | No | No | No | Yes | No |
| LPR/ANPR | Yes | Yes | No | No | No | Yes | No |
| Heat mapping | Yes | No | No | Yes | No | No | No |
| AI search | Yes | Yes | Yes | No | No | No | No |
| Slip/fall detection | Yes | No | No | No | No | No | No |
| Weapons detection | Yes | No | No | No | No | No | No |
| Camera-agnostic | Yes | No | Yes | No | Yes | Yes | Yes |
| HIPAA-compliant | Yes | No | No | No | No | No | No |
| Mobile app | Yes | Yes | Yes | Yes | Yes | Yes | No |
| Access control | Yes | Yes | No | No | Yes | Yes | No |
| Multi-domain | All 4 | Sec+Retail | Sec | Retail | Retail+Bank | Security | Security |
| Price | Self-hosted | $500-3K/cam | Sub/cam | $200-500/mo | Enterprise | Enterprise | Free |
| GPU required | No | N/A | N/A | N/A | N/A | N/A | Optional |

**Unique differentiators vs all competitors:**
1. Only platform with ABA therapy video analytics
2. Only platform spanning healthcare + retail + security from one codebase
3. Self-hosted with consent-based facial recognition (privacy-first)
4. CPU-capable (no GPU required for core features)
5. Slip/fall and weapons detection (no competitor offers prominently)
6. HIPAA-compliant by architecture, not by add-on
