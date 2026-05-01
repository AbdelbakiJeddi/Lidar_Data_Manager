"""Node API routes for octree node operations."""
import logging
import tempfile
import os
import shutil
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from minio import Minio

from app.api.dependencies import get_db, get_minio
from app.repositories import DatasetRepository, OctreeNodeRepository
from app.core.minio_client import BUCKET_PROCESSED, download_file
from app.services.pdal_processor import PDALProcessor
from app.models.bounding_box import BoundingBox

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


@router.post("/{dataset_id}/zone")
async def download_zone(
    dataset_id: str,
    bbox: BoundingBox,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio)
) -> Response:
    """
    Download merged point cloud for a specific zone.

    User provides bounding box → server retrieves intersecting nodes,
    crops each to exact bbox, merges, and returns file.
    """
    node_repo = OctreeNodeRepository(db)
    dataset_repo = DatasetRepository(db)

    # Validate dataset exists
    dataset = await dataset_repo.get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    # Get nodes intersecting bbox
    nodes = await node_repo.get_nodes_in_bbox(dataset_id, bbox)

    if not nodes:
        raise HTTPException(status_code=404, detail="No nodes found in specified zone")

    pdal = PDALProcessor(require_available=False)
    if not pdal.pdal_version:
        raise HTTPException(status_code=503, detail="PDAL not available")

    # Create temp directory for downloads and processing
    temp_dir = tempfile.mkdtemp(prefix="zone_")
    downloaded_files = []
    cropped_files = []

    try:
        # Download all nodes from MinIO
        for node in nodes:
            local_path = os.path.join(temp_dir, f"node_{node['node_id']}.laz")
            download_file(minio_client, BUCKET_PROCESSED, node["minio_path"], local_path)
            downloaded_files.append(local_path)

        # Crop each node to exact bbox
        for i, local_path in enumerate(downloaded_files):
            cropped_path = os.path.join(temp_dir, f"cropped_{i}.laz")
            pdal.crop_to_bbox(local_path, cropped_path, bbox)
            cropped_files.append(cropped_path)

        # Merge all cropped files
        merged_path = os.path.join(temp_dir, "merged.laz")
        pdal.merge_files(cropped_files, merged_path)

        # Read file content
        with open(merged_path, "rb") as f:
            content = f.read()

        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename=zone_{dataset_id}.laz"}
        )

    except Exception as e:
        logger.error(f"Zone download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temp files
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
