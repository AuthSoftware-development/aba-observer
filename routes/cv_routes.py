"""CV pipeline routes — cv/analyze, cv/recognize, cv/vehicles, cameras CRUD, camera snapshot/cv, WebSocket live feed."""

import asyncio
import base64
import json
import shutil
import time
import uuid
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, Header, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

from security.audit import log_event
from security.encryption import secure_delete
from routes.helpers import (
    UPLOAD_DIR,
    _client_ip,
    _get_camera_manager,
    _require_auth,
)

router = APIRouter()


@router.post("/api/cv/analyze")
async def cv_analyze_video(
    request: Request,
    video: UploadFile = File(...),
    confidence: float = Form(0.5),
    sample_fps: float = Form(5.0),
    authorization: str | None = Header(None),
):
    """Run CV person detection + tracking on an uploaded video."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    video_id = uuid.uuid4().hex[:8]
    ext = Path(video.filename).suffix or ".mp4"
    video_path = UPLOAD_DIR / f"cv_{video_id}{ext}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    try:
        from cv.pipeline import CVPipeline
        pipeline = CVPipeline(confidence=confidence)
        results = pipeline.analyze_video(video_path, sample_fps=sample_fps)

        log_event("cv_analyze", user=user["sub"], role=user["role"], ip=_client_ip(request),
                  details={
                      "video": video.filename,
                      "people_found": results["summary"]["total_unique_people"],
                  })
        return results
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        secure_delete(video_path)


@router.post("/api/cv/analyze-existing/{filename}")
async def cv_analyze_existing(
    filename: str,
    request: Request,
    confidence: float = 0.5,
    sample_fps: float = 5.0,
    authorization: str | None = Header(None),
):
    """Run CV analysis on a video already uploaded for AI analysis."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    # Check uploads directory
    video_path = UPLOAD_DIR / filename
    if not video_path.exists():
        return JSONResponse({"error": "Video not found"}, status_code=404)

    try:
        from cv.pipeline import CVPipeline
        pipeline = CVPipeline(confidence=confidence)
        results = pipeline.analyze_video(video_path, sample_fps=sample_fps)
        return results
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ====== CAMERA MANAGEMENT ROUTES ======

@router.get("/api/cameras")
async def list_cameras(request: Request, authorization: str | None = Header(None)):
    """List all connected cameras."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    return _get_camera_manager().list_cameras()


@router.post("/api/cameras")
async def add_camera(request: Request, authorization: str | None = Header(None)):
    """Add and connect to an RTSP camera."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    body = await request.json()
    camera_id = body.get("camera_id", "").strip()
    name = body.get("name", "").strip()
    rtsp_url = body.get("rtsp_url", "").strip()

    if not camera_id or not rtsp_url:
        return JSONResponse({"error": "camera_id and rtsp_url required"}, status_code=400)

    from ingest.rtsp import CameraConfig
    config = CameraConfig(
        camera_id=camera_id,
        name=name or camera_id,
        rtsp_url=rtsp_url,
        fps_target=body.get("fps_target", 5.0),
    )

    try:
        cam = _get_camera_manager().add_camera(config)
        log_event("add_camera", user=user["sub"], role=user["role"], ip=_client_ip(request),
                  details={"camera_id": camera_id, "name": name})
        return cam.status()
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)


@router.delete("/api/cameras/{camera_id}")
async def remove_camera(camera_id: str, request: Request, authorization: str | None = Header(None)):
    """Disconnect and remove a camera."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    if _get_camera_manager().remove_camera(camera_id):
        log_event("remove_camera", user=user["sub"], role=user["role"], ip=_client_ip(request),
                  details={"camera_id": camera_id})
        return {"removed": camera_id}
    return JSONResponse({"error": "Camera not found"}, status_code=404)


@router.get("/api/cameras/{camera_id}/snapshot")
async def camera_snapshot(camera_id: str, request: Request, authorization: str | None = Header(None)):
    """Get current frame from a camera as JPEG."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    cam = _get_camera_manager().get_camera(camera_id)
    if not cam:
        return JSONResponse({"error": "Camera not found"}, status_code=404)

    jpeg = cam.get_snapshot()
    if not jpeg:
        return JSONResponse({"error": "No frame available"}, status_code=503)

    return Response(content=jpeg, media_type="image/jpeg")


@router.get("/api/cameras/{camera_id}/cv")
async def camera_cv_frame(camera_id: str, request: Request, authorization: str | None = Header(None)):
    """Run CV detection on the latest frame from a camera."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    cam = _get_camera_manager().get_camera(camera_id)
    if not cam:
        return JSONResponse({"error": "Camera not found"}, status_code=404)

    frame = cam.latest_frame
    if frame is None:
        return JSONResponse({"error": "No frame available"}, status_code=503)

    from cv.pipeline import CVPipeline
    pipeline = CVPipeline()
    result = pipeline.process_frame(frame)
    return result


@router.post("/api/cv/recognize")
async def recognize_faces_in_video(
    request: Request,
    video: UploadFile = File(...),
    sample_fps: float = Form(1.0),
    authorization: str | None = Header(None),
):
    """Run face recognition on an uploaded video.

    Identifies consented/enrolled faces by name, labels others as "Person A/B/C".
    """
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    video_id = uuid.uuid4().hex[:8]
    ext = Path(video.filename).suffix or ".mp4"
    video_path = UPLOAD_DIR / f"face_{video_id}{ext}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    try:
        from cv.face import FaceRecognizer
        from store.consent import load_all_enrolled

        recognizer = FaceRecognizer()
        enrolled = load_all_enrolled()
        recognizer.load_enrolled(enrolled)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return JSONResponse({"error": "Cannot open video"}, status_code=400)

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = max(1, int(video_fps / sample_fps))

        timeline = []
        all_people = {}  # name -> {role, identified, appearances}
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = round(frame_idx / video_fps, 2)
                faces = recognizer.recognize_frame(frame)

                for face in faces:
                    name = face["name"]
                    if name not in all_people:
                        all_people[name] = {
                            "role": face["role"],
                            "identified": face["identified"],
                            "consent_id": face["consent_id"],
                            "appearances": 0,
                            "first_seen": timestamp,
                            "last_seen": timestamp,
                        }
                    all_people[name]["appearances"] += 1
                    all_people[name]["last_seen"] = timestamp

                if faces:
                    timeline.append({
                        "timestamp": timestamp,
                        "faces": [{
                            "name": f["name"],
                            "identified": f["identified"],
                            "confidence": f["confidence"],
                            "similarity": f["similarity"],
                            "bbox": list(f["bbox"]),
                        } for f in faces],
                    })

            frame_idx += 1

        cap.release()

        log_event("face_recognize", user=user["sub"], role=user["role"], ip=_client_ip(request),
                  details={"video": video.filename, "people_found": len(all_people),
                           "identified": sum(1 for p in all_people.values() if p["identified"])})

        return {
            "people": all_people,
            "enrolled_count": len(enrolled),
            "timeline": timeline,
            "frames_analyzed": len(timeline),
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        secure_delete(video_path)


@router.post("/api/cv/vehicles")
async def detect_vehicles(
    request: Request,
    video: UploadFile = File(...),
    sample_fps: float = Form(1.0),
    authorization: str | None = Header(None),
):
    """Detect and count vehicles in a video."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    video_id = uuid.uuid4().hex[:8]
    ext = Path(video.filename).suffix or ".mp4"
    video_path = UPLOAD_DIR / f"veh_{video_id}{ext}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    try:
        from cv.vehicle import VehicleDetector
        detector = VehicleDetector()
        results = detector.analyze_video(str(video_path), sample_fps=sample_fps)
        return results
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        secure_delete(video_path)


# ====== WEBSOCKET LIVE FEED ======

@router.websocket("/ws/cameras/{camera_id}/live")
async def camera_live_feed(websocket: WebSocket, camera_id: str):
    """WebSocket endpoint for live camera feed with CV detection overlay.

    Streams JPEG frames with person detection data at ~5 FPS.
    Client receives JSON messages: {"frame": base64_jpeg, "cv": {...detection data...}}

    Auth: Send {"token": "..."} as first message after connect.
    """
    await websocket.accept()

    # Auth check — first message must be token
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        token = auth_msg.get("token", "")
        from security.auth import verify_token
        user = verify_token(token)
        if not user:
            await websocket.send_json({"error": "Authentication required"})
            await websocket.close(code=4001)
            return
    except (asyncio.TimeoutError, Exception):
        await websocket.send_json({"error": "Send {\"token\": \"...\"} to authenticate"})
        await websocket.close(code=4001)
        return

    cam = _get_camera_manager().get_camera(camera_id)
    if not cam:
        await websocket.send_json({"error": f"Camera '{camera_id}' not found"})
        await websocket.close(code=4004)
        return

    from cv.pipeline import CVPipeline
    pipeline = CVPipeline(confidence=0.4)

    try:
        while True:
            frame = cam.latest_frame
            if frame is not None:
                cv_result = pipeline.process_frame(frame)
                _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                frame_b64 = base64.b64encode(jpeg.tobytes()).decode()

                await websocket.send_json({
                    "frame": frame_b64,
                    "cv": cv_result,
                    "camera_id": camera_id,
                    "timestamp": time.time(),
                })

            await asyncio.sleep(0.2)  # ~5 FPS
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
