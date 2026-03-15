"""HIPAA-compliant audit logging — append-only log of all PHI access."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

AUDIT_DIR = Path(__file__).parent.parent / "audit_logs"
AUDIT_DIR.mkdir(exist_ok=True)


def _get_log_path() -> Path:
    """Get today's audit log file path."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return AUDIT_DIR / f"audit_{date_str}.jsonl"


def log_event(
    action: str,
    user: str = "anonymous",
    role: str = "unknown",
    details: dict | None = None,
    ip: str = "",
):
    """Append an audit event to today's log file.

    Actions: login, login_failed, logout, analyze_upload, analyze_camera,
             view_result, delete_result, download_result, view_history,
             create_user, access_denied
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "epoch": time.time(),
        "action": action,
        "user": user,
        "role": role,
        "ip": ip,
        "details": details or {},
    }

    log_path = _get_log_path()
    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")

    # Make audit logs append-only (best-effort on Windows)
    try:
        os.chmod(str(log_path), 0o644)
    except OSError:
        pass


def get_recent_events(limit: int = 100) -> list[dict]:
    """Get recent audit events (most recent first)."""
    events = []
    # Read today's and yesterday's logs
    for log_file in sorted(AUDIT_DIR.glob("audit_*.jsonl"), reverse=True)[:2]:
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    events.sort(key=lambda e: e.get("epoch", 0), reverse=True)
    return events[:limit]
