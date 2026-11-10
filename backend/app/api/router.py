"""Root router: mounts every API version under settings.api_prefix (/api)."""
from fastapi import APIRouter

from ..config import settings
from .v1.router import router as v1_router

api_router = APIRouter(prefix=settings.api_prefix)
api_router.include_router(v1_router)
