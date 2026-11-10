from fastapi import APIRouter

from . import auth, meta, plans, youtube

router = APIRouter(prefix="/v1")
router.include_router(meta.router)
router.include_router(auth.router)
router.include_router(plans.router)
router.include_router(youtube.router)
