"""Security domain routes — security/analyze, alerts, access-control, tailgating."""

import shutil
import uuid
from pathlib import Path

import numpy as np
from fastapi import APIRouter, File, Form, Header, Request, UploadFile
from fastapi.responses import JSONResponse

from security.audit import log_event
from security.encryption import secure_delete
from routes.helpers import UPLOAD_DIR, _client_ip, _require_auth

router = APIRouter()


@router.post("/api/security/analyze")
async def security_analyze_video(
    request: Request,
    video: UploadFile = File(...),
    confidence: float = Form(0.5),
    sample_fps: float = Form(2.0),
    authorization: str | None = Header(None),
):
    """Run security analysis on a video — safety events, vehicles, anomalies."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    video_id = uuid.uuid4().hex[:8]
    ext = Path(video.filename).suffix or ".mp4"
    video_path = UPLOAD_DIR / f"sec_{video_id}{ext}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    try:
        from cv.pipeline import CVPipeline
        from cv.safety import SafetyDetector
        from cv.vehicle import VehicleDetector

        # Run person detection + tracking
        pipeline = CVPipeline(confidence=confidence)
        cv_results = pipeline.analyze_video(video_path, sample_fps=sample_fps)

        # Run safety analysis using tracking data
        safety = SafetyDetector()
        all_safety_events = []
        for snap in cv_results["timeline"]:
            tracks = snap.get("tracks", {})
            events = safety.analyze_with_tracks(
                np.zeros((1, 1, 3), dtype=np.uint8),  # Dummy frame for motion (tracks have the data)
                {int(k): v for k, v in tracks.items()},
                snap["timestamp"],
            )
            all_safety_events.extend(events)

        # Run vehicle detection
        vehicle_det = VehicleDetector(confidence_threshold=confidence)
        vehicle_results = vehicle_det.analyze_video(str(video_path), sample_fps=sample_fps)

        # Process alerts
        from domains.security.alerts import AlertEngine
        engine = AlertEngine()
        fired_alerts = engine.process_events(all_safety_events)

        log_event("security_analyze", user=user["sub"], role=user["role"], ip=_client_ip(request),
                  details={"video": video.filename,
                           "safety_events": len(all_safety_events),
                           "vehicles": vehicle_results["summary"]["max_concurrent_vehicles"],
                           "alerts_fired": len(fired_alerts)})

        return {
            "cv": cv_results["summary"],
            "video_info": cv_results["video_info"],
            "safety_events": all_safety_events,
            "safety_summary": {
                "total_events": len(all_safety_events),
                "by_type": {},
            },
            "vehicles": vehicle_results["summary"],
            "alerts_fired": fired_alerts,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        secure_delete(video_path)


@router.get("/api/security/alerts")
async def list_security_alerts(request: Request, authorization: str | None = Header(None)):
    """List configured alert rules."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from domains.security.alerts import list_alert_rules
    return list_alert_rules()


@router.post("/api/security/alerts")
async def create_security_alert(request: Request, authorization: str | None = Header(None)):
    """Create a new alert rule."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    body = await request.json()
    from domains.security.alerts import create_alert_rule
    rule = create_alert_rule(body)

    log_event("create_alert_rule", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"rule_id": rule["rule_id"], "event_type": rule.get("event_type")})
    return rule


@router.delete("/api/security/alerts/{rule_id}")
async def delete_security_alert(rule_id: str, request: Request, authorization: str | None = Header(None)):
    """Delete an alert rule."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    from domains.security.alerts import delete_alert_rule
    if not delete_alert_rule(rule_id):
        return JSONResponse({"error": "Rule not found"}, status_code=404)
    return {"deleted": rule_id}


@router.get("/api/security/alerts/history")
async def get_alert_history(
    request: Request,
    date: str = "",
    authorization: str | None = Header(None),
):
    """Get alert history."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from domains.security.alerts import AlertEngine
    engine = AlertEngine()
    return engine.get_alert_history(date=date or None)


@router.post("/api/access-control/webhook")
async def access_control_webhook(request: Request, authorization: str | None = Header(None)):
    """Receive access control events (door/badge)."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    body = await request.json()
    from domains.security.access_control import record_access_event
    event = record_access_event(body)

    log_event("access_event", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"type": event["event_type"], "door": event.get("door_id")})
    return {"recorded": event["event_id"]}


@router.get("/api/access-control/events")
async def get_access_events(
    request: Request,
    date: str = "",
    door_id: str = "",
    authorization: str | None = Header(None),
):
    """Get access control events."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from domains.security.access_control import get_access_events
    return get_access_events(date=date or None, door_id=door_id or None)


@router.get("/api/access-control/tailgating")
async def detect_tailgating_events(
    request: Request,
    date: str = "",
    authorization: str | None = Header(None),
):
    """Detect possible tailgating from access events."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from domains.security.access_control import get_access_events, detect_tailgating
    events = get_access_events(date=date or None, limit=1000)
    return detect_tailgating(events)
