import logging

from fastapi import APIRouter, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    """Health check response model."""

    status: str
    version: str = "1.0.0"


class ReadyStatus(BaseModel):
    """Readiness check response model."""

    status: str
    services: dict[str, str]
    version: str = "1.0.0"


@router.get(
    "/health",
    response_model=HealthStatus,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Returns 200 if the application process is running",
)
async def health_check() -> HealthStatus:
    """Liveness probe - indicates the process is running."""
    return HealthStatus(status="healthy")


@router.get(
    "/ready",
    response_model=ReadyStatus,
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    description="Returns 200 if all dependencies are ready",
)
async def ready_check() -> ReadyStatus:
    """Readiness probe - checks if dependencies are ready."""
    services = {}
    all_ready = True

    # Check Firestore connectivity
    try:
        from google.cloud import firestore

        db = firestore.Client()
        # Try a simple operation
        db.collection("_health_check").document("test").get()
        services["firestore"] = "connected"
    except Exception as e:
        logger.warning(f"Firestore not ready: {e}")
        services["firestore"] = "disconnected"
        all_ready = False

    # Check Pub/Sub connectivity
    try:
        from google.cloud import pubsub_v1

        # Just verify we can create a client
        _ = pubsub_v1.PublisherClient()
        services["pubsub"] = "connected"
    except Exception as e:
        logger.warning(f"Pub/Sub not ready: {e}")
        services["pubsub"] = "disconnected"
        all_ready = False

    status_str = "ready" if all_ready else "not_ready"

    return ReadyStatus(status=status_str, services=services)
