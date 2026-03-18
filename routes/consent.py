"""Consent & face recognition enrollment routes."""

import cv2
import numpy as np
from fastapi import APIRouter, File, Header, Request, UploadFile
from fastapi.responses import JSONResponse

from security.audit import log_event
from routes.helpers import _client_ip, _require_auth

router = APIRouter()


@router.get("/api/consent")
async def list_consent_records(
    request: Request,
    domain: str = "",
    authorization: str | None = Header(None),
):
    """List all consent records."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from store.consent import list_consents
    records = list_consents(domain=domain or None)
    log_event("view_consent_list", user=user["sub"], role=user["role"], ip=_client_ip(request))
    return records


@router.post("/api/consent")
async def create_consent_record(request: Request, authorization: str | None = Header(None)):
    """Create a new consent record for face recognition enrollment."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] not in ("admin", "bcba"):
        return JSONResponse({"error": "Admin or BCBA only"}, status_code=403)

    body = await request.json()
    person_name = body.get("person_name", "").strip()
    domain = body.get("domain", "").strip()
    role = body.get("role", "").strip()
    consent_source = body.get("consent_source", "").strip()

    if not person_name or not domain or not role:
        return JSONResponse({"error": "person_name, domain, and role required"}, status_code=400)
    if domain not in ("aba", "retail", "security", "custom"):
        return JSONResponse({"error": "domain must be aba, retail, security, or custom"}, status_code=400)

    from store.consent import create_consent
    record = create_consent(
        person_name=person_name,
        domain=domain,
        role=role,
        consent_source=consent_source or "admin_created",
        cameras=body.get("cameras"),
        expires_at=body.get("expires_at"),
        guardian_name=body.get("guardian_name"),
        notes=body.get("notes", ""),
    )

    log_event("create_consent", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"consent_id": record["consent_id"], "person": person_name, "domain": domain})
    return record


@router.get("/api/consent/{consent_id}")
async def get_consent_record(consent_id: str, request: Request, authorization: str | None = Header(None)):
    """Get a specific consent record."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    from store.consent import get_consent
    record = get_consent(consent_id)
    if not record:
        return JSONResponse({"error": "Consent not found"}, status_code=404)
    return record


@router.delete("/api/consent/{consent_id}")
async def revoke_consent_record(consent_id: str, request: Request, authorization: str | None = Header(None)):
    """Revoke consent and securely delete all face embeddings."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] not in ("admin", "bcba"):
        return JSONResponse({"error": "Admin or BCBA only"}, status_code=403)

    from store.consent import revoke_consent
    if not revoke_consent(consent_id):
        return JSONResponse({"error": "Consent not found"}, status_code=404)

    log_event("revoke_consent", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"consent_id": consent_id})
    return {"revoked": consent_id}


@router.post("/api/consent/{consent_id}/enroll")
async def enroll_face(
    consent_id: str,
    request: Request,
    photos: list[UploadFile] = File(...),
    authorization: str | None = Header(None),
):
    """Enroll face embeddings from uploaded photos.

    Upload 3-5 photos of the person from different angles for best accuracy.
    Only works if a valid, non-revoked consent record exists.
    """
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] not in ("admin", "bcba"):
        return JSONResponse({"error": "Admin or BCBA only"}, status_code=403)

    from store.consent import get_consent, save_embeddings

    record = get_consent(consent_id)
    if not record:
        return JSONResponse({"error": "Consent not found"}, status_code=404)
    if record.get("revoked"):
        return JSONResponse({"error": "Consent has been revoked"}, status_code=400)

    try:
        from cv.face import FaceRecognizer
        recognizer = FaceRecognizer()

        all_embeddings = []
        for photo in photos:
            contents = await photo.read()
            nparr = np.frombuffer(contents, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            embeddings = recognizer.enroll_from_frame(img)
            all_embeddings.extend(embeddings)

        if not all_embeddings:
            return JSONResponse({"error": "No faces detected in uploaded photos"}, status_code=400)

        save_embeddings(consent_id, all_embeddings)

        log_event("enroll_face", user=user["sub"], role=user["role"], ip=_client_ip(request),
                  details={"consent_id": consent_id, "person": record["person_name"],
                           "photos": len(photos), "embeddings": len(all_embeddings)})

        return {
            "consent_id": consent_id,
            "person_name": record["person_name"],
            "embeddings_stored": len(all_embeddings),
            "photos_processed": len(photos),
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
