"""Shared route helpers — auth, logging, common utilities."""

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from security.auth import verify_token
from security.audit import log_event


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
        log_event("access_denied", user="anonymous", ip=_client_ip(request))
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    return user


def _client_ip(request: Request) -> str:
    """Get client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def auth_headers():
    """Helper for client-side fetch — returns auth header dict."""
    return {}
