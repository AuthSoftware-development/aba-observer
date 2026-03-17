"""Access control integration — correlate door/badge events with video."""

import json
import time
from pathlib import Path

ACCESS_DIR = Path(__file__).parent.parent.parent / "access_events"


def _ensure_dir():
    ACCESS_DIR.mkdir(exist_ok=True)


def record_access_event(event: dict) -> dict:
    """Record an access control event from a door/badge system.

    Expected fields:
        event_id: str
        timestamp: str or float
        door_id: str
        badge_id: str (optional)
        person_name: str (optional)
        event_type: str ("entry", "exit", "denied", "forced", "propped")
        source: str ("hid", "lenel", "brivo", "wiegand", "generic")
    """
    _ensure_dir()
    event.setdefault("event_id", f"ac_{int(time.time() * 1000)}")
    event.setdefault("timestamp", time.time())
    event.setdefault("event_type", "entry")
    event.setdefault("source", "generic")
    event["received_at"] = time.time()

    date_str = time.strftime("%Y-%m-%d")
    log_path = ACCESS_DIR / f"access_{date_str}.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")

    return event


def get_access_events(date: str | None = None, door_id: str | None = None, limit: int = 100) -> list[dict]:
    """Get access events, optionally filtered by door."""
    _ensure_dir()
    date_str = date or time.strftime("%Y-%m-%d")
    log_path = ACCESS_DIR / f"access_{date_str}.jsonl"

    if not log_path.exists():
        return []

    events = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if door_id and event.get("door_id") != door_id:
                continue
            events.append(event)

    return events[-limit:]


def detect_tailgating(events: list[dict], time_window: float = 3.0) -> list[dict]:
    """Detect possible tailgating — multiple entries through same door within time window.

    Tailgating = someone following an authorized person through a secured door
    without swiping their own badge.

    Args:
        events: Access events sorted by timestamp
        time_window: Seconds within which multiple entries suggest tailgating
    """
    tailgating = []
    door_events = {}  # door_id → last entry timestamp

    for event in events:
        if event.get("event_type") != "entry":
            continue

        door = event.get("door_id", "")
        ts = event.get("timestamp", 0)
        if isinstance(ts, str):
            try:
                from datetime import datetime
                ts = datetime.fromisoformat(ts).timestamp()
            except Exception:
                ts = event.get("received_at", 0)

        if door in door_events:
            last_ts = door_events[door]["timestamp"]
            gap = ts - last_ts
            if 0 < gap < time_window:
                tailgating.append({
                    "type": "possible_tailgating",
                    "severity": "medium",
                    "door_id": door,
                    "gap_seconds": round(gap, 2),
                    "first_entry": door_events[door],
                    "second_entry": event,
                    "description": f"Two entries at {door} within {gap:.1f}s — possible tailgating",
                })

        door_events[door] = {"timestamp": ts, **event}

    return tailgating
