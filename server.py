"""FastAPI server for ABA Observer — HIPAA-secured web UI."""

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from security.audit import log_event
from security.auth import (
    SESSION_TIMEOUT,
    create_token,
    create_user,
    refresh_token,
    setup_required,
    verify_pin,
    verify_token,
)
from security.encryption import decrypt_json, encrypt_json, secure_delete

app = FastAPI(title="ABA Observer", version="0.4.0")

BEHAVIOR_LIBRARY_PATH = Path(__file__).parent / "configs" / "behavior_library.json"

# Restrict CORS to same-origin + local network only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost:3017",
        "http://localhost:3017",
        "https://127.0.0.1:3017",
    ],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

UPLOAD_DIR = Path(__file__).parent / "uploads"
OUTPUT_DIR = Path(__file__).parent / "output"
CONFIGS_DIR = Path(__file__).parent / "configs"
STATIC_DIR = Path(__file__).parent / "static"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Serve static files (login page is public, app requires auth via JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ====== AUTH HELPERS ======

def _get_user(authorization: str | None) -> dict | None:
    """Extract user from Authorization header."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    return verify_token(token)


def _require_auth(authorization: str | None, request: Request) -> dict | JSONResponse:
    """Require valid auth. Returns user dict or error response."""
    user = _get_user(authorization)
    if not user:
        ip = request.client.host if request.client else ""
        log_event("access_denied", ip=ip, details={"path": str(request.url.path)})
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    return user


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


# ====== SECURITY HEADERS ======

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


# ====== PUBLIC ROUTES ======

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/auth/status")
async def auth_status():
    """Check if setup is needed (no users yet)."""
    return {"setup_required": setup_required(), "session_timeout": SESSION_TIMEOUT}


@app.post("/api/auth/setup")
async def auth_setup(request: Request):
    """First-time setup: create admin user."""
    if not setup_required():
        return JSONResponse({"error": "Setup already complete"}, status_code=400)
    body = await request.json()
    username = body.get("username", "").strip()
    pin = body.get("pin", "").strip()
    if not username or len(pin) < 4:
        return JSONResponse({"error": "Username required, PIN must be 4+ characters"}, status_code=400)
    create_user(username, pin, role="admin")
    token = create_token(username, "admin")
    log_event("create_user", user=username, role="admin", ip=_client_ip(request),
              details={"first_setup": True})
    return {"token": token, "username": username, "role": "admin", "timeout": SESSION_TIMEOUT}


@app.post("/api/auth/login")
async def auth_login(request: Request):
    """Login with username + PIN."""
    body = await request.json()
    username = body.get("username", "").strip()
    pin = body.get("pin", "").strip()
    ip = _client_ip(request)

    user = verify_pin(username, pin)
    if not user:
        log_event("login_failed", user=username, ip=ip)
        return JSONResponse({"error": "Invalid username or PIN"}, status_code=401)

    token = create_token(user["username"], user["role"])
    log_event("login", user=user["username"], role=user["role"], ip=ip)
    return {"token": token, "username": user["username"], "role": user["role"], "timeout": SESSION_TIMEOUT}


@app.post("/api/auth/refresh")
async def auth_refresh(authorization: str | None = Header(None)):
    """Refresh an active session token."""
    if not authorization:
        return JSONResponse({"error": "No token"}, status_code=401)
    token = authorization.replace("Bearer ", "")
    new_token = refresh_token(token)
    if not new_token:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    return {"token": new_token}


@app.post("/api/auth/create-user")
async def auth_create_user(request: Request, authorization: str | None = Header(None)):
    """Admin: create a new user."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    body = await request.json()
    username = body.get("username", "").strip()
    pin = body.get("pin", "").strip()
    role = body.get("role", "rbt")
    if not username or len(pin) < 4:
        return JSONResponse({"error": "Username required, PIN 4+ chars"}, status_code=400)
    if role not in ("admin", "bcba", "rbt"):
        return JSONResponse({"error": "Role must be admin, bcba, or rbt"}, status_code=400)

    if not create_user(username, pin, role):
        return JSONResponse({"error": "Username already exists"}, status_code=409)

    log_event("create_user", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"new_user": username, "new_role": role})
    return {"created": username, "role": role}


# ====== PROTECTED ROUTES ======

@app.get("/api/providers")
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

    try:
        import torch
        qwen_available = torch.cuda.is_available()
        qwen_reason = None if qwen_available else "No CUDA GPU"
    except ImportError:
        qwen_available = False
        qwen_reason = "PyTorch not installed"

    providers.append({
        "name": "qwen",
        "label": "Qwen2.5-Omni (Local/HIPAA-Safe)",
        "available": qwen_available,
        "hipaa_warning": None,
        "reason": qwen_reason,
    })
    return providers


@app.get("/api/configs")
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


@app.get("/api/configs/{filename}")
async def get_config(filename: str, request: Request, authorization: str | None = Header(None)):
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    path = CONFIGS_DIR / filename
    if not path.exists() or path.suffix != ".json":
        return JSONResponse({"error": "Config not found"}, status_code=404)
    with open(path) as f:
        return json.load(f)


@app.post("/api/configs")
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


def _run_analysis(video_path: Path, provider_name: str, config_name: str) -> dict:
    """Shared analysis logic."""
    client_config = None
    if config_name:
        config_path = CONFIGS_DIR / config_name
        if config_path.exists():
            with open(config_path) as f:
                client_config = json.load(f)

    from prompts.aba_system import build_system_prompt
    system_prompt = build_system_prompt(client_config)

    if provider_name == "gemini":
        from providers.gemini import GeminiProvider
        ai_provider = GeminiProvider()
    elif provider_name == "qwen":
        from providers.qwen import QwenProvider
        ai_provider = QwenProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_name}")

    if not ai_provider.is_available():
        raise RuntimeError(f"Provider '{provider_name}' is not available")

    return ai_provider.analyze_video(video_path, system_prompt)


def _save_encrypted_result(data: dict, metadata: dict, name_prefix: str) -> str:
    """Encrypt and save analysis result. Returns filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name_prefix}_{timestamp}.enc"
    out_path = OUTPUT_DIR / filename

    payload = {"results": data, "metadata": metadata}
    encrypted = encrypt_json(payload)
    out_path.write_text(encrypted)
    return filename


def _load_encrypted_result(filename: str) -> dict | None:
    """Load and decrypt an analysis result."""
    path = OUTPUT_DIR / filename
    if not path.exists():
        return None
    try:
        return decrypt_json(path.read_text())
    except Exception:
        # Fallback: try reading as plain JSON (legacy unencrypted files)
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return None


@app.post("/api/analyze")
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


@app.post("/api/analyze-recording")
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


@app.get("/api/history")
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


@app.get("/api/history/{filename}")
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


@app.delete("/api/history/{filename}")
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


@app.get("/api/audit")
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

@app.get("/api/behavior-library")
async def get_behavior_library(request: Request, authorization: str | None = Header(None)):
    """Get the full behavior library for voice command matching."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if BEHAVIOR_LIBRARY_PATH.exists():
        with open(BEHAVIOR_LIBRARY_PATH) as f:
            return json.load(f)
    return {"maladaptive_behaviors": [], "replacement_behaviors": [], "interventions": []}


@app.post("/api/configs/{filename}/add-behavior")
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


@app.delete("/api/configs/{filename}/behaviors/{behavior_name}")
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


@app.post("/api/configs/{filename}/fuzzy-match")
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


if __name__ == "__main__":
    import ssl
    import uvicorn
    from security.tls import ensure_certs

    cert_path, key_path = ensure_certs()

    print("\n" + "=" * 50)
    print("  ABA Observer — HIPAA-Secured")
    print("=" * 50)

    if cert_path and key_path:
        print(f"  HTTPS: https://localhost:3017")
        print(f"  TLS:   Self-signed certificate")
        uvicorn.run(app, host="0.0.0.0", port=3017,
                    ssl_certfile=cert_path, ssl_keyfile=key_path)
    else:
        print(f"  HTTP:  http://localhost:3017")
        print(f"  WARNING: No TLS — use a reverse proxy in production")
        uvicorn.run(app, host="0.0.0.0", port=3017)
