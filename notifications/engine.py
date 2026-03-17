"""Notification delivery engine — routes alerts to email, webhook, or log."""

import json
import smtplib
import time
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path


class NotificationEngine:
    """Deliver notifications through configured channels."""

    def __init__(self, config: dict | None = None):
        """
        Config:
            smtp_host, smtp_port, smtp_user, smtp_pass, smtp_from
            webhook_timeout (seconds)
        """
        self._config = config or {}
        self._log_dir = Path(__file__).parent.parent / "alerts"
        self._log_dir.mkdir(exist_ok=True)

    def deliver(self, alert: dict):
        """Deliver an alert through all configured channels."""
        channels = alert.get("notify", ["log"])
        results = {}

        for channel in channels:
            if channel == "log":
                results["log"] = self._deliver_log(alert)
            elif channel == "webhook":
                results["webhook"] = self._deliver_webhook(alert)
            elif channel == "email":
                results["email"] = self._deliver_email(alert)

        return results

    def _deliver_log(self, alert: dict) -> bool:
        """Write alert to log file."""
        date_str = time.strftime("%Y-%m-%d")
        log_path = self._log_dir / f"notifications_{date_str}.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "channel": "log",
                "delivered_at": time.time(),
                "alert": alert,
            }, default=str) + "\n")
        return True

    def _deliver_webhook(self, alert: dict) -> bool:
        """POST alert to a webhook URL."""
        url = alert.get("webhook_url")
        if not url:
            return False

        try:
            data = json.dumps(alert, default=str).encode()
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            timeout = self._config.get("webhook_timeout", 10)
            urllib.request.urlopen(req, timeout=timeout)
            return True
        except Exception as e:
            print(f"[notify] Webhook failed: {e}")
            return False

    def _deliver_email(self, alert: dict) -> bool:
        """Send alert via email (SMTP)."""
        smtp_host = self._config.get("smtp_host")
        if not smtp_host:
            print("[notify] Email not configured (no smtp_host)")
            return False

        try:
            event = alert.get("event", {})
            subject = f"[The I Alert] {event.get('type', 'Unknown')} — {event.get('severity', 'unknown')} severity"
            body = f"""
Security Alert from The I — Intelligent Video Analytics

Type: {event.get('type', 'Unknown')}
Severity: {event.get('severity', 'unknown')}
Description: {event.get('description', 'No description')}
Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.get('timestamp', 0)))}
Track ID: {event.get('track_id', 'N/A')}
Confidence: {event.get('confidence', 'N/A')}

Rule: {alert.get('rule_name', 'N/A')} ({alert.get('rule_id', 'N/A')})

---
This is an automated alert from The I platform.
"""
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self._config.get("smtp_from", "thei@localhost")
            msg["To"] = self._config.get("smtp_to", "admin@localhost")

            with smtplib.SMTP(smtp_host, self._config.get("smtp_port", 587)) as server:
                if self._config.get("smtp_tls", True):
                    server.starttls()
                user = self._config.get("smtp_user")
                if user:
                    server.login(user, self._config.get("smtp_pass", ""))
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"[notify] Email failed: {e}")
            return False
