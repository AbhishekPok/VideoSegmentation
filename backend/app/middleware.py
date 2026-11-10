"""HTTP middleware: CSRF guard, security headers, request logging."""
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import settings
from .core.logging import get_logger

log = get_logger("app.request")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "planner"

# Allows the YouTube player (length auto-detect) and Google Fonts; everything else is same-origin.
CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' https://www.youtube.com https://s.ytimg.com",
        "frame-src https://www.youtube.com https://www.youtube-nocookie.com",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src https://fonts.gstatic.com",
        "img-src 'self' data: https://i.ytimg.com",
        "connect-src 'self'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


def register_middleware(app: FastAPI) -> None:
    api = settings.api_prefix + "/"
    docs = settings.api_prefix + "/docs"

    @app.middleware("http")
    async def request_pipeline(request: Request, call_next):
        start = time.perf_counter()
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        path = request.url.path

        # CSRF: state-changing API calls must carry a custom header. Browsers only let
        # same-origin scripts set it (CORS is not enabled), so cross-site forms are rejected.
        if request.method in UNSAFE_METHODS and path.startswith(api) and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
            response = JSONResponse({"detail": "Missing X-Requested-With header"}, status_code=403)
        else:
            response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if not path.startswith(docs):  # Swagger UI loads its own CDN assets
            response.headers.setdefault("Content-Security-Policy", CSP)
        if path.startswith(api):
            response.headers.setdefault("Cache-Control", "no-store")

        if path.startswith(api):
            log.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
        return response
