"""Health check API routes."""
import logging
from fastapi import APIRouter, Depends
from minio import Minio

from app.api.dependencies import get_minio
from app.core.minio_client import check_minio_health
from app.core.mongo_client import check_mongo_health

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health(minio_client: Minio = Depends(get_minio)) -> dict:
    """Check health of all services."""
    minio_health = check_minio_health(minio_client)
    mongo_health = await check_mongo_health()
    
    # Determine overall status
    status = "ok"
    if minio_health.get("status") != "healthy":
        status = "degraded"
    if mongo_health.get("status") != "healthy":
        status = "degraded"
    
    return {
        "status": status,
        "minio": minio_health,
        "mongodb": mongo_health
    }
