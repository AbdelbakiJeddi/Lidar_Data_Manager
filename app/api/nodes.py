"""Node API routes for octree node operations."""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from minio import Minio

from app.api.dependencies import get_db, get_minio
from app.repositories import DatasetRepository, OctreeNodeRepository
from app.core.minio_client import BUCKET_PROCESSED

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lidar/nodes", tags=["nodes"])


@router.get("/{dataset_id}/{node_id}/download")
async def download_node(
    dataset_id: str,
    node_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio)
) -> StreamingResponse:
    """Download a specific octree node file."""
    node_repo = OctreeNodeRepository(db)

    node = await node_repo.get_node(dataset_id, node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    try:
        response = minio_client.get_object(BUCKET_PROCESSED, node["minio_path"])
        return StreamingResponse(
            response,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename=node_{node_id}.laz"}
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{dataset_id}/{node_id}")
async def get_node_info(
    dataset_id: str,
    node_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """Get node metadata."""
    node_repo = OctreeNodeRepository(db)
    
    node = await node_repo.get_node(dataset_id, node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    
    return node
