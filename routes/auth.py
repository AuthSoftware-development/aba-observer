"""Auth routes — setup, login, refresh, create-user, reset-pin."""

import os

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from security.audit import log_event
from security.auth import (
    SESSION_TIMEOUT,
    create_token,
    create_user,
    refresh_token,
    reset_pin,
    setup_required,
    verify_pin,
)
from routes.helpers import _require_auth, _client_ip
from routes.models import SetupRequest, LoginRequest, CreateUserRequest, ResetPinRequest

router = APIRouter()

# Rate limiter — created here, imported by server.py
limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.environ.get("RATE_LIMIT_ENABLED", "true").lower() != "false",
)


@router.get("/api/auth/status")
async def auth_status():
    """Check if setup is needed (no users yet)."""
    return {"setup_required": setup_required(), "session_timeout": SESSION_TIMEOUT}


@router.post("/api/auth/setup")
@limiter.limit("5/minute")
async def auth_setup(request: Request):
    """First-time setup: create admin user."""
    if not setup_required():
        return JSONResponse({"error": "Setup already complete"}, status_code=400)
    body = SetupRequest(**(await request.json()))
    create_user(body.username, body.pin, role="admin")
    token = create_token(body.username, "admin")
    log_event("create_user", user=body.username, role="admin", ip=_client_ip(request),
              details={"first_setup": True})
    return {"token": token, "username": body.username, "role": "admin", "timeout": SESSION_TIMEOUT}


@router.post("/api/auth/login")
@limiter.limit("10/minute")
async def auth_login(request: Request):
    """Login with username + PIN."""
    body = LoginRequest(**(await request.json()))
    ip = _client_ip(request)

    user = verify_pin(body.username, body.pin)
    if not user:
        log_event("login_failed", user=body.username, ip=ip)
        return JSONResponse({"error": "Invalid username or PIN"}, status_code=401)

    token = create_token(user["username"], user["role"])
    log_event("login", user=user["username"], role=user["role"], ip=ip)
    return {"token": token, "username": user["username"], "role": user["role"], "timeout": SESSION_TIMEOUT}


@router.post("/api/auth/refresh")
async def auth_refresh(authorization: str | None = Header(None)):
    """Refresh an active session token."""
    if not authorization:
        return JSONResponse({"error": "No token"}, status_code=401)
    token = authorization.replace("Bearer ", "")
    new_token = refresh_token(token)
    if not new_token:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    return {"token": new_token}


@router.post("/api/auth/create-user")
async def auth_create_user(request: Request, authorization: str | None = Header(None)):
    """Admin: create a new user."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user
    if user["role"] != "admin":
        return JSONResponse({"error": "Admin only"}, status_code=403)

    body = CreateUserRequest(**(await request.json()))
    if not create_user(body.username, body.pin, body.role):
        return JSONResponse({"error": "Username already exists"}, status_code=409)

    log_event("create_user", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"new_user": body.username, "new_role": body.role})
    return {"created": body.username, "role": body.role}


@router.post("/api/auth/reset-pin")
async def auth_reset_pin(request: Request, authorization: str | None = Header(None)):
    """Reset a user's PIN. Admins can reset any user; users can reset their own."""
    user = _require_auth(authorization, request)
    if isinstance(user, JSONResponse):
        return user

    body = ResetPinRequest(**(await request.json()))
    target_user = body.username.strip()
    is_self = target_user == user["sub"]
    is_admin = user["role"] == "admin"

    if not target_user:
        target_user = user["sub"]
        is_self = True

    if not is_admin:
        if not is_self:
            return JSONResponse({"error": "Only admins can reset other users' PINs"}, status_code=403)
        if not body.current_pin:
            return JSONResponse({"error": "Current PIN required"}, status_code=400)
        if not verify_pin(target_user, body.current_pin):
            return JSONResponse({"error": "Current PIN is incorrect"}, status_code=401)

    if not reset_pin(target_user, body.new_pin):
        return JSONResponse({"error": "User not found"}, status_code=404)

    log_event("reset_pin", user=user["sub"], role=user["role"], ip=_client_ip(request),
              details={"target_user": target_user, "self_reset": is_self})
    return {"reset": target_user}
