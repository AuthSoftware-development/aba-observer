"""Retail domain routes — retail/analyze, stores, POS."""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, Request, UploadFile
from fastapi.responses import JSONResponse

from security.audit import log_event
from security.encryption import secure_delete
from routes.helpers import UPLOAD_DIR, _client_ip, _require_auth

router = APIRouter()


@router.post("/api/retail/analyze")
async def retail_analyze_video(
    request: Request,
    video: UploadFile = File(...),
    store_id: str = Form(""),
    confidence: float = Form(0.5),
    sample_fps: float = Form(2.0),
    authorization: str | None = Header(None),
):
    """Run retail analytics (traffic, dwell, occupancy, heatmap) on a video."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    video_id = uuid.uuid4().hex[:8]
    ext = Path(video.filename).suffix or ".mp4"
    video_path = UPLOAD_DIR / f"retail_{video_id}{ext}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    try:
        from cv.pipeline import CVPipeline
        from domains.retail.metrics import RetailMetrics
        from domains.retail.config import get_store_config

        # Load store config if provided
        store_config = get_store_config(store_id) if store_id else None
        capacity = store_config.get("capacity", 0) if store_config else 0

        # Run CV pipeline
        pipeline = CVPipeline(confidence=confidence)
        if store_config and store_config.get("zones"):
            from cv.zones import Zone
            for z in store_config["zones"]:
                pipeline.zones.add_zone(Zone.from_dict(z))

        cv_results = pipeline.analyze_video(video_path, sample_fps=sample_fps)

        # Compute retail metrics
        metrics = RetailMetrics(capacity=capacity)
        retail_results = metrics.compute_from_timeline(
            cv_results["timeline"],
            zones_defined=cv_results.get("zones_defined"),
        )

        log_event("retail_analyze", user=user["sub"], role=user["role"], ip=_client_ip(request),
                  details={"video": video.filename, "store": store_id,
                           "visitors": retail_results["traffic"]["total_visitors"]})

        return {
            "cv": cv_results["summary"],
            "video_info": cv_results["video_info"],
            "retail": retail_results,
            "store_id": store_id or None,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        secure_delete(video_path)


@router.get("/api/retail/stores")
async def list_stores(request: Request, authorization: str | None = Header(None)):
    """List all configured retail stores."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from domains.retail.config import list_store_configs
    return list_store_configs()


@router.post("/api/retail/stores")
async def create_store(request: Request, authorization: str | None = Header(None)):
    """Create or update a retail store configuration."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    body = await request.json()
    store_id = body.get("store_id", "").strip()
    if not store_id:
        return JSONResponse({"error": "store_id required"}, status_code=400)

    from domains.retail.config import save_store_config
    config = save_store_config(store_id, body)

    log_event("create_store", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"store_id": store_id})
    return config


@router.get("/api/retail/stores/{store_id}")
async def get_store(store_id: str, request: Request, authorization: str | None = Header(None)):
    """Get a retail store configuration."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from domains.retail.config import get_store_config
    config = get_store_config(store_id)
    if not config:
        return JSONResponse({"error": "Store not found"}, status_code=404)
    return config


@router.post("/api/pos/webhook")
async def pos_webhook(request: Request, authorization: str | None = Header(None)):
    """Receive POS transaction events (webhook endpoint)."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    body = await request.json()
    from domains.retail.pos import record_transaction
    tx = record_transaction(body)

    log_event("pos_transaction", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"type": tx["type"], "total": tx["total"], "register": tx["register_id"]})
    return {"recorded": tx["transaction_id"], "type": tx["type"]}


@router.get("/api/pos/transactions")
async def get_pos_transactions(
    request: Request,
    date: str = "",
    limit: int = 100,
    authorization: str | None = Header(None),
):
    """Get POS transactions for a date."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from domains.retail.pos import get_transactions
    return get_transactions(date=date or None, limit=limit)


@router.get("/api/pos/exceptions")
async def get_pos_exceptions(
    request: Request,
    date: str = "",
    authorization: str | None = Header(None),
):
    """Get flagged suspicious transactions."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from domains.retail.pos import get_exceptions
    return get_exceptions(date=date or None)


@router.get("/api/pos/conversion")
async def get_conversion_rate(
    request: Request,
    traffic: int = 0,
    date: str = "",
    authorization: str | None = Header(None),
):
    """Compute conversion rate (transactions / foot traffic)."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from domains.retail.pos import compute_conversion_rate
    return compute_conversion_rate(traffic_count=traffic, date=date or None)
