# Changelog

All notable changes to the Observer Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- PIN reset endpoint (`POST /api/auth/reset-pin`) — self-service with current PIN verification, admin can reset any user without current PIN
- **CV Pipeline (Phase 2):** Person detection using MobileNet-SSD (CPU-only, no GPU required)
- Centroid-based multi-object tracking — persistent person IDs across frames
- Zone management — define polygon ROI areas, check person presence in zones
- CV analysis endpoint (`POST /api/cv/analyze`) — upload video for person detection + tracking
- RTSP camera ingest module — connect to IP cameras with auto-reconnect
- Camera management API (`GET/POST/DELETE /api/cameras`) — add, list, remove cameras
- Camera snapshot endpoint (`GET /api/cameras/{id}/snapshot`) — get current frame as JPEG
- Live CV detection endpoint (`GET /api/cameras/{id}/cv`) — run detection on latest camera frame
- System spec (`docs/SYSTEM_SPEC.md`) and changelog

## [0.4.0] - 2026-03-14

### Added
- Full HIPAA security stack: TLS, PIN auth, AES-256-GCM encryption, audit logging
- Web UI with login, video upload, camera recording, data history, audit log
- Google Gemini provider (cloud, with HIPAA warning)
- Qwen2.5-Omni provider (local, HIPAA-safe)
- ABC chain detection from video analysis
- Behavior frequency counting with timestamps
- Prompt level tracking
- Per-client behavior target configurations
- Behavior library with fuzzy matching for voice commands
- Session summary generation (setting, people, duration, notes)
- Role-based access control (admin, bcba, rbt)
- Secure video deletion (overwrite before unlink)
- CLI interface for non-authenticated analysis

### Fixed
- Cached torch/Qwen status at startup to prevent async event loop blocking
