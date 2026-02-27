from fastapi import APIRouter

from api.health import router as health_router
from api.webhooks import router as webhooks_router

router = APIRouter()
router.include_router(health_router)
router.include_router(webhooks_router)
