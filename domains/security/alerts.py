"""Security alert engine — configurable rules, severity levels, notification routing."""

import json
import time
from pathlib import Path
from collections import defaultdict

ALERTS_DIR = Path(__file__).parent.parent.parent / "alerts"


def _ensure_dir():
    ALERTS_DIR.mkdir(exist_ok=True)


def create_alert_rule(rule: dict) -> dict:
    """Create an alert rule.

    Rule format:
        rule_id: str
        name: str
        event_type: str ("possible_fall", "loitering", "crowd_forming", etc.)
        severity_min: str ("low", "medium", "high")
        enabled: bool
        notify: list[str] (["log", "webhook", "email"])
        webhook_url: str (optional)
        cooldown_seconds: int (minimum time between alerts of same type)
    """
    _ensure_dir()
    rule.setdefault("rule_id", f"rule_{int(time.time())}")
    rule.setdefault("enabled", True)
    rule.setdefault("notify", ["log"])
    rule.setdefault("cooldown_seconds", 300)  # 5 min default
    rule.setdefault("created_at", time.time())

    path = ALERTS_DIR / f"{rule['rule_id']}.json"
    with open(path, "w") as f:
        json.dump(rule, f, indent=2)
    return rule


def list_alert_rules() -> list[dict]:
    """List all alert rules."""
    _ensure_dir()
    rules = []
    for f in ALERTS_DIR.glob("rule_*.json"):
        with open(f) as fh:
            rules.append(json.load(fh))
    return rules


def delete_alert_rule(rule_id: str) -> bool:
    """Delete an alert rule."""
    path = ALERTS_DIR / f"{rule_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


class AlertEngine:
    """Process security events and fire alerts based on configured rules."""

    def __init__(self):
        self._rules = []
        self._last_fired = defaultdict(float)  # event_type → last fire timestamp
        self._alert_log = []

    def load_rules(self):
        """Load rules from disk."""
        self._rules = list_alert_rules()

    def process_events(self, events: list[dict]) -> list[dict]:
        """Process security events and return fired alerts.

        Args:
            events: List of events from SafetyDetector

        Returns:
            List of alerts that should be delivered
        """
        if not self._rules:
            self.load_rules()

        severity_order = {"low": 0, "medium": 1, "high": 2}
        fired = []

        for event in events:
            event_type = event.get("type", "")
            event_severity = event.get("severity", "low")

            for rule in self._rules:
                if not rule.get("enabled"):
                    continue
                if rule.get("event_type") != event_type:
                    continue

                # Check severity threshold
                min_sev = rule.get("severity_min", "low")
                if severity_order.get(event_severity, 0) < severity_order.get(min_sev, 0):
                    continue

                # Check cooldown
                cooldown = rule.get("cooldown_seconds", 300)
                last = self._last_fired.get(f"{rule['rule_id']}_{event_type}", 0)
                now = time.time()
                if now - last < cooldown:
                    continue

                # Fire alert
                alert = {
                    "rule_id": rule["rule_id"],
                    "rule_name": rule.get("name", ""),
                    "event": event,
                    "notify": rule.get("notify", ["log"]),
                    "webhook_url": rule.get("webhook_url"),
                    "fired_at": now,
                }
                fired.append(alert)
                self._last_fired[f"{rule['rule_id']}_{event_type}"] = now

                # Log alert
                self._log_alert(alert)

        return fired

    def _log_alert(self, alert: dict):
        """Append alert to log file."""
        _ensure_dir()
        date_str = time.strftime("%Y-%m-%d")
        log_path = ALERTS_DIR / f"alert_log_{date_str}.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(alert, default=str) + "\n")

    def get_alert_history(self, date: str | None = None, limit: int = 100) -> list[dict]:
        """Get alert history for a date."""
        _ensure_dir()
        date_str = date or time.strftime("%Y-%m-%d")
        log_path = ALERTS_DIR / f"alert_log_{date_str}.jsonl"

        if not log_path.exists():
            return []

        alerts = []
        with open(log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    alerts.append(json.loads(line))

        return alerts[-limit:]
