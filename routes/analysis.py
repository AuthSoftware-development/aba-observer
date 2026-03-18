"""AI analysis routes — providers, configs, analyze, history, behavior library."""

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, Request, UploadFile
from fastapi.responses import JSONResponse

from security.audit import log_event
from security.encryption import secure_delete
from routes.helpers import (
    BEHAVIOR_LIBRARY_PATH,
    CONFIGS_DIR,
    OUTPUT_DIR,
    UPLOAD_DIR,
    _QWEN_STATUS,
    _client_ip,
    _load_encrypted_result,
    _require_auth,
    _run_analysis,
    _save_encrypted_result,
)

router = APIRouter()


@router.get("/api/providers")
async def list_providers(request: Request, authorization: str | None = Header(None)):
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    providers = []
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    gemini_available = bool(api_key)
    try:
        from google import genai  # noqa: F401
        gemini_sdk = True
    except ImportError:
        gemini_sdk = False

    providers.append({
        "name": "gemini",
        "label": "Google Gemini (Cloud)",
        "available": gemini_available and gemini_sdk,
        "hipaa_warning": "No BAA — video is processed on Google servers. Not HIPAA-safe for production PHI.",
        "reason": None if (gemini_available and gemini_sdk)
                  else "No API key" if not gemini_available else "SDK not installed",
    })

    # Qwen availability is cached at startup to avoid blocking the event loop
    qwen_available = _QWEN_STATUS["available"]
    qwen_reason = _QWEN_STATUS["reason"]

    providers.append({
        "name": "qwen",
        "label": "Qwen2.5-Omni (Local/HIPAA-Safe)",
        "available": qwen_available,
        "hipaa_warning": None,
        "reason": qwen_reason,
    })
    return providers


@router.get("/api/configs")
async def list_configs(request: Request, authorization: str | None = Header(None)):
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    configs = []
    for f in CONFIGS_DIR.glob("*.json"):
        with open(f) as fh:
            data = json.load(fh)
        configs.append({
            "filename": f.name,
            "client_id": data.get("client_id", f.stem),
            "targets": len(data.get("behavior_targets", [])),
            "replacements": len(data.get("replacement_behaviors", [])),
            "skills": len(data.get("skill_acquisition_targets", [])),
        })
    return configs


@router.get("/api/configs/{filename}")
async def get_config(filename: str, request: Request, authorization: str | None = Header(None)):
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    path = CONFIGS_DIR / filename
    if not path.exists() or path.suffix != ".json":
        return JSONResponse({"error": "Config not found"}, status_code=404)
    with open(path) as f:
        return json.load(f)


@router.post("/api/configs")
async def save_config(request: Request, authorization: str | None = Header(None)):
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    config = await request.json()
    client_id = config.get("client_id", f"client_{uuid.uuid4().hex[:6]}")
    filename = f"{client_id.lower().replace(' ', '_')}.json"
    path = CONFIGS_DIR / filename
    with open(path, "w") as f:
        json.dump(config, f, indent=2)

    log_event("save_config", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"config": filename})
    return {"filename": filename, "client_id": client_id}


@router.post("/api/analyze")
async def analyze_video(
    request: Request,
    video: UploadFile = File(...),
    provider: str = Form("gemini"),
    config: str = Form(""),
    authorization: str | None = Header(None),
):
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    video_id = uuid.uuid4().hex[:8]
    ext = Path(video.filename).suffix or ".mp4"
    video_path = UPLOAD_DIR / f"{video_id}{ext}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    file_size_mb = video_path.stat().st_size / 1024 / 1024

    try:
        data = _run_analysis(video_path, provider, config)
    except Exception as e:
        log_event("analyze_upload", user=user["sub"], role=user["role"], ip=_client_ip(request),
                  details={"error": str(e), "provider": provider})
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        secure_delete(video_path)

    metadata = {
        "source": "upload",
        "video_name": video.filename,
        "video_size_mb": round(file_size_mb, 1),
        "provider": provider,
        "config": config or None,
        "analyzed_by": user["sub"],
        "analyzed_at": datetime.now().isoformat(),
    }

    out_file = _save_encrypted_result(data, metadata, Path(video.filename).stem)

    log_event("analyze_upload", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"provider": provider, "config": config, "output": out_file,
                       "size_mb": round(file_size_mb, 1)})

    return {"results": data, "metadata": {**metadata, "output_file": out_file}}


@router.post("/api/analyze-recording")
async def analyze_recording(
    request: Request,
    recording: UploadFile = File(...),
    provider: str = Form("gemini"),
    config: str = Form(""),
    source: str = Form("camera"),
    authorization: str | None = Header(None),
):
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    video_id = uuid.uuid4().hex[:8]
    ext = ".webm" if "webm" in (recording.content_type or "") else ".mp4"
    video_path = UPLOAD_DIR / f"rec_{video_id}{ext}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(recording.file, f)

    file_size_mb = video_path.stat().st_size / 1024 / 1024

    try:
        data = _run_analysis(video_path, provider, config)
    except Exception as e:
        log_event("analyze_camera", user=user["sub"], role=user["role"], ip=_client_ip(request),
                  details={"error": str(e), "provider": provider})
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        secure_delete(video_path)

    metadata = {
        "source": source,
        "video_size_mb": round(file_size_mb, 1),
        "provider": provider,
        "config": config or None,
        "analyzed_by": user["sub"],
        "analyzed_at": datetime.now().isoformat(),
    }

    out_file = _save_encrypted_result(data, metadata, "recording")

    log_event("analyze_camera", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"provider": provider, "output": out_file})

    return {"results": data, "metadata": {**metadata, "output_file": out_file}}


@router.get("/api/history")
async def list_history(request: Request, authorization: str | None = Header(None)):
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    log_event("view_history", user=user["sub"], role=user["role"], ip=_client_ip(request))

    results = []
    for f in sorted(OUTPUT_DIR.glob("*.enc"), reverse=True):
        data = _load_encrypted_result(f.name)
        if not data:
            continue
        inner = data.get("results", data)
        meta = data.get("metadata", {})
        session = inner.get("session_summary", {})
        results.append({
            "filename": f.name,
            "source": meta.get("source", "upload"),
            "provider": meta.get("provider", "unknown"),
            "analyzed_at": meta.get("analyzed_at", ""),
            "analyzed_by": meta.get("analyzed_by", ""),
            "setting": session.get("setting", ""),
            "events": len(inner.get("events", [])),
            "chains": len(inner.get("abc_chains", [])),
            "config": meta.get("config"),
        })

    # Also include legacy unencrypted .json files
    for f in sorted(OUTPUT_DIR.glob("*.json"), reverse=True):
        try:
            with open(f) as fh:
                raw = json.load(fh)
            inner = raw.get("results", raw)
            meta = raw.get("metadata", {})
            session = inner.get("session_summary", {})
            results.append({
                "filename": f.name,
                "source": meta.get("source", "upload"),
                "provider": meta.get("provider", "unknown"),
                "analyzed_at": meta.get("analyzed_at", ""),
                "analyzed_by": meta.get("analyzed_by", ""),
                "setting": session.get("setting", ""),
                "events": len(inner.get("events", [])),
                "chains": len(inner.get("abc_chains", [])),
                "config": meta.get("config"),
            })
        except Exception:
            continue

    results.sort(key=lambda r: r.get("analyzed_at", ""), reverse=True)
    return results


@router.get("/api/history/{filename}")
async def get_history(filename: str, request: Request, authorization: str | None = Header(None)):
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    data = _load_encrypted_result(filename)
    if not data:
        return JSONResponse({"error": "Not found"}, status_code=404)

    log_event("view_result", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"filename": filename})

    if "results" in data:
        return data
    return {"results": data, "metadata": {}}


@router.delete("/api/history/{filename}")
async def delete_history(filename: str, request: Request, authorization: str | None = Header(None)):
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    path = OUTPUT_DIR / filename
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)

    secure_delete(path)

    log_event("delete_result", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"filename": filename})
    return {"deleted": filename}


@router.get("/api/audit")
async def get_audit_log(request: Request, authorization: str | None = Header(None)):
    """Admin only: view audit log."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    from security.audit import get_recent_events
    return get_recent_events(limit=200)


# ====== BEHAVIOR LIBRARY ======

@router.get("/api/behavior-library")
async def get_behavior_library(request: Request, authorization: str | None = Header(None)):
    """Get the full behavior library for voice command matching."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if BEHAVIOR_LIBRARY_PATH.exists():
        with open(BEHAVIOR_LIBRARY_PATH) as f:
            return json.load(f)
    return {"maladaptive_behaviors": [], "replacement_behaviors": [], "interventions": []}


@router.post("/api/configs/{filename}/add-behavior")
async def add_behavior_to_config(filename: str, request: Request, authorization: str | None = Header(None)):
    """Add a behavior to a client config. Supports fuzzy matching from library."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    path = CONFIGS_DIR / filename
    if not path.exists():
        return JSONResponse({"error": "Config not found"}, status_code=404)

    body = await request.json()
    behavior_id = body.get("behavior_id", "").strip()
    custom_name = body.get("custom_name", "").strip()
    custom_definition = body.get("custom_definition", "").strip()
    category = body.get("category", "maladaptive")  # maladaptive, replacement, skill

    with open(path) as f:
        config = json.load(f)

    # Try to find in library first
    library = {}
    if BEHAVIOR_LIBRARY_PATH.exists():
        with open(BEHAVIOR_LIBRARY_PATH) as f:
            library = json.load(f)

    entry = None
    if behavior_id:
        # Search library by ID or fuzzy alias match
        for cat_key in ["maladaptive_behaviors", "replacement_behaviors"]:
            for b in library.get(cat_key, []):
                if b["id"] == behavior_id:
                    entry = b
                    break
                # Fuzzy alias match
                all_names = [b["id"], b["name"].lower()] + [a.lower() for a in b.get("aliases", [])]
                if behavior_id.lower() in all_names:
                    entry = b
                    category = "replacement" if cat_key == "replacement_behaviors" else "maladaptive"
                    break
            if entry:
                break

    if entry:
        new_behavior = {
            "name": entry["id"],
            "operational_definition": entry["operational_definition"],
            "library_id": entry["id"],
        }
    elif custom_name:
        new_behavior = {
            "name": custom_name.lower().replace(" ", "_"),
            "operational_definition": custom_definition or f"Instances of {custom_name} as identified by the observer.",
        }
    else:
        return JSONResponse({"error": "Provide behavior_id or custom_name"}, status_code=400)

    # Add to appropriate list in config
    if category == "replacement":
        key = "replacement_behaviors"
    elif category == "skill":
        key = "skill_acquisition_targets"
        new_behavior["description"] = new_behavior.pop("operational_definition")
        new_behavior["mastery_criteria"] = "80% across 3 consecutive sessions"
    else:
        key = "behavior_targets"

    if key not in config:
        config[key] = []

    # Check for duplicates
    existing_names = [b["name"] for b in config[key]]
    if new_behavior["name"] in existing_names:
        return JSONResponse({"error": f"'{new_behavior['name']}' already tracked for this client"}, status_code=409)

    config[key].append(new_behavior)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)

    log_event("add_behavior", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"config": filename, "behavior": new_behavior["name"], "category": category})
    return {"added": new_behavior, "category": category, "total": len(config[key])}


@router.delete("/api/configs/{filename}/behaviors/{behavior_name}")
async def remove_behavior_from_config(filename: str, behavior_name: str, request: Request, authorization: str | None = Header(None)):
    """Remove a behavior from a client config."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    path = CONFIGS_DIR / filename
    if not path.exists():
        return JSONResponse({"error": "Config not found"}, status_code=404)

    with open(path) as f:
        config = json.load(f)

    removed = False
    for key in ["behavior_targets", "replacement_behaviors", "skill_acquisition_targets"]:
        before = len(config.get(key, []))
        config[key] = [b for b in config.get(key, []) if b["name"] != behavior_name]
        if len(config[key]) < before:
            removed = True
            break

    if not removed:
        return JSONResponse({"error": f"Behavior '{behavior_name}' not found"}, status_code=404)

    with open(path, "w") as f:
        json.dump(config, f, indent=2)

    log_event("remove_behavior", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"config": filename, "behavior": behavior_name})
    return {"removed": behavior_name}


@router.post("/api/configs/{filename}/fuzzy-match")
async def fuzzy_match_behavior(filename: str, request: Request, authorization: str | None = Header(None)):
    """Fuzzy-match a voice command phrase against the behavior library."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    body = await request.json()
    phrase = body.get("phrase", "").strip().lower()
    if not phrase:
        return JSONResponse({"error": "No phrase provided"}, status_code=400)

    library = {}
    if BEHAVIOR_LIBRARY_PATH.exists():
        with open(BEHAVIOR_LIBRARY_PATH) as f:
            library = json.load(f)

    matches = []
    for cat_key, cat_label in [("maladaptive_behaviors", "maladaptive"), ("replacement_behaviors", "replacement")]:
        for b in library.get(cat_key, []):
            score = 0
            all_names = [b["id"].replace("_", " "), b["name"].lower()] + [a.lower() for a in b.get("aliases", [])]
            for name in all_names:
                if phrase == name:
                    score = 100
                    break
                if phrase in name or name in phrase:
                    score = max(score, 80)
                # Word overlap
                phrase_words = set(phrase.split())
                name_words = set(name.split())
                overlap = phrase_words & name_words
                if overlap:
                    score = max(score, int(60 * len(overlap) / max(len(phrase_words), len(name_words))))

            if score > 0:
                matches.append({
                    "id": b["id"],
                    "name": b["name"],
                    "category": cat_label,
                    "score": score,
                    "operational_definition": b["operational_definition"],
                })

    # Sort by score descending
    matches.sort(key=lambda m: m["score"], reverse=True)
    return {"phrase": phrase, "matches": matches[:5]}
