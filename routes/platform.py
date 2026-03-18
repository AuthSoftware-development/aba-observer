"""Platform routes — system/status, cameras/discover, notifications/test, api-keys, compliance."""

import time
from pathlib import Path

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from security.audit import log_event
from routes.helpers import (
    OUTPUT_DIR,
    UPLOAD_DIR,
    _client_ip,
    _get_camera_manager,
    _require_auth,
)

router = APIRouter()


@router.get("/api/system/status")
async def system_status(request: Request, authorization: str | None = Header(None)):
    """System health: cameras, resources, search index, domain status."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    import platform

    cameras = _get_camera_manager().list_cameras()
    from search.engine import get_event_stats
    search_stats_data = get_event_stats()

    # Resource usage
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(Path(__file__).parent.parent))
        resources = {
            "cpu_percent": cpu,
            "memory_used_gb": round(mem.used / (1024**3), 1),
            "memory_total_gb": round(mem.total / (1024**3), 1),
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
        }
    except ImportError:
        resources = {"note": "Install psutil for resource monitoring"}

    return {
        "platform": "The I — Intelligent Video Analytics",
        "version": "0.5.0",
        "python": platform.python_version(),
        "os": f"{platform.system()} {platform.release()}",
        "cameras": {
            "total": len(cameras),
            "connected": sum(1 for c in cameras if c.get("connected")),
            "list": cameras,
        },
        "search_index": search_stats_data,
        "resources": resources,
        "domains": {
            "aba": {"status": "active", "endpoints": 5},
            "retail": {"status": "active", "endpoints": 6},
            "security": {"status": "active", "endpoints": 7},
        },
        "storage": {
            "encrypted_results": len(list(OUTPUT_DIR.glob("*.enc"))),
            "upload_files": len(list(UPLOAD_DIR.glob("*"))),
        },
    }


@router.get("/api/cameras/discover")
async def discover_cameras_endpoint(request: Request, authorization: str | None = Header(None)):
    """Auto-discover ONVIF cameras on the local network."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    from ingest.onvif_discovery import discover_cameras
    cameras = discover_cameras(timeout=5.0)

    log_event("camera_discovery", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"found": len(cameras)})
    return {"discovered": cameras, "count": len(cameras)}


@router.post("/api/notifications/test")
async def test_notification(request: Request, authorization: str | None = Header(None)):
    """Send a test notification through configured channels."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    body = await request.json()
    channel = body.get("channel", "log")

    from notifications.engine import NotificationEngine
    engine = NotificationEngine(config=body.get("config", {}))

    test_alert = {
        "rule_id": "test",
        "rule_name": "Test Notification",
        "event": {
            "type": "test",
            "severity": "low",
            "description": "This is a test notification from The I",
            "timestamp": time.time(),
        },
        "notify": [channel],
        "webhook_url": body.get("webhook_url"),
    }

    results = engine.deliver(test_alert)
    return {"channel": channel, "delivered": results}


# ====== API KEY MANAGEMENT ======

@router.post("/api/api-keys")
async def create_api_key_endpoint(request: Request, authorization: str | None = Header(None)):
    """Create a new API key for third-party integrations."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "Name required"}, status_code=400)

    from security.api_keys import create_api_key
    result = create_api_key(
        name=name,
        created_by=user["sub"],
        scopes=body.get("scopes"),
        expires_at=body.get("expires_at"),
    )

    log_event("create_api_key", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"key_id": result["key_id"], "name": name, "scopes": body.get("scopes")})
    return result


@router.get("/api/api-keys")
async def list_api_keys_endpoint(request: Request, authorization: str | None = Header(None)):
    """List all API keys (secrets not shown)."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    from security.api_keys import list_api_keys
    return list_api_keys()


@router.delete("/api/api-keys/{key_id}")
async def revoke_api_key_endpoint(key_id: str, request: Request, authorization: str | None = Header(None)):
    """Revoke an API key."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    from security.api_keys import revoke_api_key
    if not revoke_api_key(key_id):
        return JSONResponse({"error": "Key not found"}, status_code=404)

    log_event("revoke_api_key", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"key_id": key_id})
    return {"revoked": key_id}


# ====== COMPLIANCE MANAGEMENT ======

@router.get("/api/compliance")
async def get_compliance(request: Request, authorization: str | None = Header(None)):
    """Get current compliance configuration."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from security.compliance import get_compliance_config
    return get_compliance_config()


@router.put("/api/compliance/{mode}")
async def update_compliance(mode: str, request: Request, authorization: str | None = Header(None)):
    """Enable/disable a compliance mode.

    Body: {"enabled": true, "settings": {...}}
    """
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    body = await request.json()
    from security.compliance import update_compliance_config
    result = update_compliance_config(
        mode=mode,
        enabled=body.get("enabled", False),
        settings=body.get("settings"),
    )

    if "error" in result:
        return JSONResponse(result, status_code=400)

    log_event("update_compliance", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"mode": mode, "enabled": body.get("enabled")})
    return result


@router.post("/api/compliance/check")
async def check_compliance_endpoint(request: Request, authorization: str | None = Header(None)):
    """Check if an action is allowed under current compliance settings.

    Body: {"action": "face_recognition", "context": {"state": "IL"}}
    """
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    body = await request.json()
    from security.compliance import check_compliance
    return check_compliance(
        action=body.get("action", ""),
        context=body.get("context"),
    )
