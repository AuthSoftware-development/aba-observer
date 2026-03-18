"""Advanced ABA routes — pose-analyze, progress, ioa, report."""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from security.audit import log_event
from security.encryption import secure_delete
from routes.helpers import (
    UPLOAD_DIR,
    _client_ip,
    _load_encrypted_result,
    _require_auth,
)

router = APIRouter()


@router.post("/api/aba/pose-analyze")
async def aba_pose_analyze(
    request: Request,
    video: UploadFile = File(...),
    sample_fps: float = Form(5.0),
    authorization: str | None = Header(None),
):
    """Analyze body pose and movement patterns in a session video.

    Detects: hand flapping, body rocking, sustained stillness, head orientation.
    """
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    video_id = uuid.uuid4().hex[:8]
    ext = Path(video.filename).suffix or ".mp4"
    video_path = UPLOAD_DIR / f"pose_{video_id}{ext}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    try:
        from cv.pose import PoseAnalyzer
        analyzer = PoseAnalyzer()
        results = analyzer.analyze_video(str(video_path), sample_fps=sample_fps)
        analyzer.close()

        log_event("pose_analyze", user=user["sub"], role=user["role"], ip=_client_ip(request),
                  details={"video": video.filename, "behaviors": results["behavior_counts"]})
        return results
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        secure_delete(video_path)


@router.get("/api/aba/progress")
async def aba_progress(
    request: Request,
    config: str = "",
    authorization: str | None = Header(None),
):
    """Get progress trends across sessions for a client."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from domains.aba.progress import get_session_history, compute_trends

    sessions = get_session_history(client_config=config or None)
    trends = compute_trends(sessions)

    log_event("view_progress", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"config": config, "sessions": len(sessions)})
    return {"sessions": sessions, "trends": trends}


@router.post("/api/aba/ioa")
async def aba_inter_observer_agreement(
    request: Request,
    authorization: str | None = Header(None),
):
    """Compare two observation sessions for inter-observer agreement (IOA).

    Body: {"session_a": "filename.enc", "session_b": "filename.enc"}
    """
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    body = await request.json()
    file_a = body.get("session_a", "")
    file_b = body.get("session_b", "")

    if not file_a or not file_b:
        return JSONResponse({"error": "session_a and session_b filenames required"}, status_code=400)

    data_a = _load_encrypted_result(file_a)
    data_b = _load_encrypted_result(file_b)

    if not data_a:
        return JSONResponse({"error": f"Session A not found: {file_a}"}, status_code=404)
    if not data_b:
        return JSONResponse({"error": f"Session B not found: {file_b}"}, status_code=404)

    from domains.aba.progress import compute_inter_observer_agreement
    results_a = data_a.get("results", data_a)
    results_b = data_b.get("results", data_b)
    ioa = compute_inter_observer_agreement(results_a, results_b)

    log_event("compute_ioa", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"session_a": file_a, "session_b": file_b,
                        "agreement": ioa["overall_agreement_pct"]})
    return ioa


@router.get("/api/aba/report/{filename}")
async def aba_generate_report(
    filename: str,
    request: Request,
    authorization: str | None = Header(None),
):
    """Generate a PDF session report for a BCBA.

    Returns PDF file download.
    """
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    data = _load_encrypted_result(filename)
    if not data:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    try:
        from domains.aba.reports import generate_session_report
        pdf_bytes = generate_session_report(data, metadata=data.get("metadata"))

        log_event("generate_report", user=user["sub"], role=user["role"], ip=_client_ip(request),
                  details={"session": filename})

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=aba_report_{filename.replace('.enc', '')}.pdf"},
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
