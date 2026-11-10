"""Domain exceptions raised by services, and the handlers that turn them into HTTP responses.

Services never import FastAPI; they raise these, and the API layer maps them to
status codes in one place.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .core.logging import get_logger

log = get_logger(__name__)


class AppError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class BadRequestError(AppError):
    status_code = 400


class AuthenticationError(AppError):
    status_code = 401


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class RateLimitError(AppError):
    status_code = 429


class UpstreamError(AppError):
    """An external service (YouTube) failed."""

    status_code = 502


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        if exc.status_code >= 500:
            log.warning("upstream error", extra={"path": request.url.path, "error": exc.message})
        return JSONResponse({"detail": exc.message}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error", extra={"path": request.url.path})
        return JSONResponse({"detail": "Internal server error"}, status_code=500)
