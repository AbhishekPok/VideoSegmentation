from fastapi import APIRouter
from sqlalchemy import text

from ...dependencies import DbSession
from ...schemas import Health, PublicConfig
from ...services import youtube_service

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=Health)
def health(db: DbSession):
    """Liveness plus a database round-trip (for load balancer health checks)."""
    db.execute(text("SELECT 1"))
    return Health(status="ok", database="ok")


@router.get("/config", response_model=PublicConfig)
def public_config():
    """Feature flags for the frontend."""
    return PublicConfig(youtube_api=youtube_service.is_configured())
