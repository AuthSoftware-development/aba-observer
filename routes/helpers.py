"""Shared route helpers — auth, logging, common utilities, shared constants."""

import json
from datetime import datetime
from pathlib import Path

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from security.auth import verify_token
from security.audit import log_event
from security.encryption import decrypt_json, encrypt_json


# ====== SHARED CONSTANTS ======

BASE_DIR = Path(__file__).parent.parent

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
CONFIGS_DIR = BASE_DIR / "configs"
STATIC_DIR = BASE_DIR / "static"
BEHAVIOR_LIBRARY_PATH = BASE_DIR / "configs" / "behavior_library.json"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ====== QWEN STATUS (cached at import time) ======

def _check_qwen_status() -> dict:
    """Check if Qwen provider is available using subprocess to avoid blocking."""
    import subprocess
    try:
        result = subprocess.run(
            ["python", "-c", "import torch; print(torch.cuda.is_available())"],
            capture_output=True, text=True, timeout=8,
        )
        if result.returncode == 0 and "True" in result.stdout:
            return {"available": True, "reason": None}
        return {"available": False, "reason": "No CUDA GPU"}
    except subprocess.TimeoutExpired:
        return {"available": False, "reason": "Check timed out"}
    except Exception:
        return {"available": False, "reason": "PyTorch not available"}


_QWEN_STATUS = _check_qwen_status()


# ====== AUTH HELPERS ======

def _get_user(authorization: str | None) -> dict | None:
    """Extract user from authorization header."""
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
    """Get client IP from request."""
    return request.client.host if request.client else ""


# ====== SHARED ANALYSIS HELPERS ======

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


# ====== CAMERA MANAGER SINGLETON ======

_camera_manager = None


def _get_camera_manager():
    global _camera_manager
    if _camera_manager is None:
        from ingest.rtsp import CameraManager
        _camera_manager = CameraManager()
    return _camera_manager


def auth_headers():
    """Helper for client-side fetch — returns auth header dict."""
    return {}
