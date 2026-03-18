"""Search routes — natural, events, index, stats, face search."""

import cv2
import numpy as np
from fastapi import APIRouter, File, Header, Request, UploadFile
from fastapi.responses import JSONResponse

from security.audit import log_event
from routes.helpers import UPLOAD_DIR, _client_ip, _require_auth

router = APIRouter()


@router.post("/api/search/natural")
async def search_natural_language(request: Request, authorization: str | None = Header(None)):
    """Natural language search across all events.

    Body: {"query": "show me all falls today", "domain": "", "limit": 50}
    """
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    body = await request.json()
    query = body.get("query", "").strip()
    if not query:
        return JSONResponse({"error": "Query required"}, status_code=400)

    from search.engine import natural_language_to_query, search_text, search_by_type, search_by_person

    parsed = natural_language_to_query(query)
    results = []

    # Try specific searches — event type takes priority over person
    if parsed.get("event_type"):
        results = search_by_type(parsed["event_type"], domain=parsed.get("domain", ""), limit=body.get("limit", 50))
    elif parsed.get("person"):
        results = search_by_type(parsed["event_type"], domain=parsed.get("domain", ""), limit=body.get("limit", 50))
    else:
        results = search_text(query, domain=body.get("domain", ""), limit=body.get("limit", 50))

    log_event("search", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"query": query, "results": len(results)})

    return {
        "query": query,
        "parsed": parsed,
        "results": results,
        "total": len(results),
    }


@router.post("/api/search/events")
async def search_events_structured(request: Request, authorization: str | None = Header(None)):
    """Structured event search with filters.

    Body: {"text": "", "event_type": "", "domain": "", "person": "", "limit": 50}
    """
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    body = await request.json()
    from search.engine import search_text, search_by_type, search_by_person

    limit = body.get("limit", 50)

    if body.get("person"):
        results = search_by_person(body["person"], limit=limit)
    elif body.get("event_type"):
        results = search_by_type(body["event_type"], domain=body.get("domain", ""), limit=limit)
    elif body.get("text"):
        results = search_text(body["text"], domain=body.get("domain", ""), limit=limit)
    else:
        results = search_text("*", domain=body.get("domain", ""), limit=limit)

    return {"results": results, "total": len(results)}


@router.post("/api/search/index")
async def index_events_endpoint(request: Request, authorization: str | None = Header(None)):
    """Manually index events into the search engine.

    Body: {"events": [list of event dicts]}
    """
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    body = await request.json()
    events = body.get("events", [])

    from search.engine import index_events
    index_events(events)

    return {"indexed": len(events)}


@router.get("/api/search/stats")
async def search_stats(request: Request, domain: str = "", authorization: str | None = Header(None)):
    """Get search index statistics."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from search.engine import get_event_stats
    return get_event_stats(domain=domain)


@router.post("/api/search/face")
async def search_face(
    request: Request,
    photo: UploadFile = File(...),
    authorization: str | None = Header(None),
):
    """Search for a person by uploading their photo.

    Only matches against consented/enrolled faces.
    """
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    contents = await photo.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse({"error": "Invalid image"}, status_code=400)

    from search.face_search import search_by_photo
    results = search_by_photo(img, video_paths=[], threshold=0.5)

    log_event("face_search", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"matched": results.get("matched", False)})
    return results


@router.get("/api/search/face/{consent_id}")
async def search_face_by_consent(
    consent_id: str,
    request: Request,
    authorization: str | None = Header(None),
):
    """Search for a consented person across available footage."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    # Search uploads directory for available videos
    video_paths = list(UPLOAD_DIR.glob("*.mp4")) + list(UPLOAD_DIR.glob("*.webm"))

    from search.face_search import search_by_consent_id
    results = search_by_consent_id(consent_id, video_paths, sample_fps=0.5)

    log_event("face_search_consent", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"consent_id": consent_id, "appearances": results.get("total_appearances", 0)})
    return results
