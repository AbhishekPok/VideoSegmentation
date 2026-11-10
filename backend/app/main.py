"""FastAPI entry point (application tier).

Run locally from the backend folder:
    .venv/bin/uvicorn app.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api.router import api_router
from .config import BACKEND_DIR, settings
from .core.logging import get_logger, setup_logging
from .exceptions import register_exception_handlers
from .middleware import register_middleware

log = get_logger(__name__)


def run_migrations() -> None:
    """Bring the database schema up to date (alembic upgrade head)."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_migrations()
    log.info("started", extra={"database": settings.database_url.split(":", 1)[0]})
    yield


def create_app() -> FastAPI:
    setup_logging(settings.log_level, settings.log_json)
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=None,
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )
    register_middleware(app)
    register_exception_handlers(app)
    app.include_router(api_router)

    # Presentation tier: serve the static frontend locally. In production nginx can
    # serve ../frontend and proxy /api to this app instead (SERVE_FRONTEND=false).
    if settings.serve_frontend and settings.frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app


app = create_app()
