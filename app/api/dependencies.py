"""API dependencies for FastAPI dependency injection."""
import logging
from typing import AsyncGenerator
from motor.motor_asyncio import AsyncIOMotorDatabase
from minio import Minio

from app.core.minio_client import get_minio_client
from app.core.mongo_client import get_database

logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Dependency to get MongoDB database instance."""
    db = await get_database()
    try:
        yield db
    finally:
        pass  # Connection managed by motor client pool


def get_minio() -> Minio:
    """Dependency to get MinIO client instance."""
    return get_minio_client()
