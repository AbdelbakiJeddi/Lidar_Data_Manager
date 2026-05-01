"""LiDAR Data Manager - Main FastAPI Application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import datasets_router, nodes_router, health_router
from app.core.minio_client import ensure_buckets, get_minio_client
from app.core.mongo_client import ensure_indexes, get_database, close_mongo_client
from app.services.pdal_processor import PDALProcessor

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize and tear down infra dependencies."""
    pdal = PDALProcessor(require_available=True)
    logger.info(f"PDAL initialized: {pdal.pdal_version}")

    minio_client = get_minio_client()
    ensure_buckets(minio_client)

    db = await get_database()
    await ensure_indexes(db)

    logger.info("Services initialized: MinIO buckets and MongoDB indexes ensured")
    try:
        yield
    finally:
        close_mongo_client()
        logger.info("Application shutdown complete")


app = FastAPI(
    title="LiDAR Data Manager",
    description="API for managing LiDAR point cloud data with octree processing",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(health_router)
app.include_router(datasets_router)
app.include_router(nodes_router)
