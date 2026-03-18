# API route modules
from routes.auth import router as auth_router
from routes.analysis import router as analysis_router
from routes.cv_routes import router as cv_router
from routes.consent import router as consent_router
from routes.retail import router as retail_router
from routes.aba import router as aba_router
from routes.security_routes import router as security_router
from routes.search import router as search_router
from routes.platform import router as platform_router

__all__ = [
    "auth_router",
    "analysis_router",
    "cv_router",
    "consent_router",
    "retail_router",
    "aba_router",
    "security_router",
    "search_router",
    "platform_router",
]
