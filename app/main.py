"""LiDAR Data Manager - Main FastAPI Application."""
import logging
from fastapi import FastAPI

from app.api import datasets_router, nodes_router, health_router
from app.core.minio_client import ensure_buckets, get_minio_client
from app.core.mongo_client import ensure_indexes, get_database

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LiDAR Data Manager",
    description="API for managing LiDAR point cloud data with octree processing",
    version="1.0.0"
)


@app.on_event("startup")
async def startup():
    """Initialize services on startup."""
    minio_client = get_minio_client()
    ensure_buckets(minio_client)
    
    db = await get_database()
    await ensure_indexes(db)
    
    logger.info("Services initialized: MinIO buckets and MongoDB indexes ensured")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    logger.info("Application shutting down")


# Include routers
app.include_router(health_router)
app.include_router(datasets_router)
app.include_router(nodes_router)
