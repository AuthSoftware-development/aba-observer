"""FastAPI server for The I — Intelligent Video Analytics."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # Load .env file

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

# Auto-download CV models on startup
from cv.models.download import check_models, download_models
if not check_models():
    print("[startup] Downloading CV model files...")
    download_models()

app = FastAPI(title="The I — Intelligent Video Analytics", version="0.5.0")

# Rate limiting — limiter is created in routes/auth.py
from routes.auth import limiter
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse({"error": "Rate limit exceeded. Try again later."}, status_code=429)


from pydantic import ValidationError

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    errors = exc.errors()
    msg = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in errors)
    return JSONResponse({"error": msg}, status_code=400)


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

STATIC_DIR = Path(__file__).parent / "static"

# Serve static files (login page is public, app requires auth via JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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


# ====== REGISTER ROUTERS ======

from routes import (
    auth_router,
    analysis_router,
    cv_router,
    consent_router,
    retail_router,
    aba_router,
    security_router,
    search_router,
    platform_router,
)

app.include_router(auth_router)
app.include_router(analysis_router)
app.include_router(cv_router)
app.include_router(consent_router)
app.include_router(retail_router)
app.include_router(aba_router)
app.include_router(security_router)
app.include_router(search_router)
app.include_router(platform_router)


# ====== OPENAPI DOCS ======
# FastAPI auto-generates OpenAPI docs at /docs (Swagger UI) and /redoc (ReDoc)
# These are available without auth for developer reference


if __name__ == "__main__":
    import uvicorn
    from security.tls import ensure_certs

    cert_path, key_path = ensure_certs()

    print("\n" + "=" * 50)
    print("  The I — Intelligent Video Analytics")
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
