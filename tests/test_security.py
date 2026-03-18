"""Tests for security domain — safety, alerts, access control, compliance."""


def test_safety_detector_loitering():
    from cv.safety import SafetyDetector
    import numpy as np

    detector = SafetyDetector()
    frame = np.zeros((300, 300, 3), dtype=np.uint8)

    # Simulate person staying in same spot for 120 seconds (needs >60s + 5 samples)
    tracks = {0: {"centroid": (150, 150), "bbox": (100, 100, 200, 200)}}
    events = []
    for t in range(0, 121, 2):  # Every 2 seconds for 120s
        result = detector.analyze_with_tracks(frame, tracks, float(t))
        events.extend(result)

    loitering = [e for e in events if e["type"] == "loitering"]
    assert len(loitering) > 0


def test_alert_rule_crud():
    from domains.security.alerts import create_alert_rule, list_alert_rules, delete_alert_rule

    rule = create_alert_rule({
        "name": "Test Rule",
        "event_type": "possible_fall",
        "severity_min": "high",
    })
    assert rule["rule_id"]

    rules = list_alert_rules()
    assert any(r["rule_id"] == rule["rule_id"] for r in rules)

    delete_alert_rule(rule["rule_id"])
    rules = list_alert_rules()
    assert not any(r["rule_id"] == rule["rule_id"] for r in rules)


def test_access_control_record():
    from domains.security.access_control import record_access_event, get_access_events

    event = record_access_event({
        "door_id": "test-door",
        "badge_id": "badge-123",
        "event_type": "entry",
        "person_name": "Test Person",
    })
    assert event["event_type"] == "entry"

    events = get_access_events()
    assert any(e.get("door_id") == "test-door" for e in events)


def test_tailgating_detection():
    from domains.security.access_control import detect_tailgating
    import time

    now = time.time()
    events = [
        {"door_id": "door-1", "badge_id": "b1", "event_type": "entry", "timestamp": now},
        {"door_id": "door-1", "badge_id": "b2", "event_type": "entry", "timestamp": now + 1.5},
    ]
    tailgating = detect_tailgating(events, time_window=3.0)
    assert len(tailgating) == 1
    assert tailgating[0]["type"] == "possible_tailgating"


def test_compliance_default_hipaa_enabled():
    from security.compliance import get_compliance_config, COMPLIANCE_FILE
    # Remove any saved config to test defaults
    if COMPLIANCE_FILE.exists():
        COMPLIANCE_FILE.unlink()
    config = get_compliance_config()
    assert config["hipaa"]["enabled"] is True
    assert config["bipa"]["enabled"] is False


def test_compliance_check_blocks_face_recognition_under_bipa():
    from security.compliance import update_compliance_config, check_compliance, get_compliance_config
    import json
    from pathlib import Path

    # Enable BIPA
    update_compliance_config("bipa", enabled=True)

    result = check_compliance("face_recognition")
    assert result["allowed"] is False
    assert "BIPA" in result["reason"]

    # Disable BIPA (cleanup)
    update_compliance_config("bipa", enabled=False)


def test_api_key_create_and_verify():
    from security.api_keys import create_api_key, verify_api_key, revoke_api_key

    result = create_api_key(
        name="Test Key",
        created_by="testadmin",
        scopes=["/api/pos"],
    )
    api_key = result["api_key"]
    assert api_key.startswith("thei_")

    # Verify with correct scope
    verified = verify_api_key(api_key, endpoint="/api/pos/webhook")
    assert verified is not None
    assert verified["name"] == "Test Key"

    # Verify with wrong scope
    denied = verify_api_key(api_key, endpoint="/api/admin")
    assert denied is None

    # Revoke
    revoke_api_key(result["key_id"])
    revoked = verify_api_key(api_key, endpoint="/api/pos/webhook")
    assert revoked is None
