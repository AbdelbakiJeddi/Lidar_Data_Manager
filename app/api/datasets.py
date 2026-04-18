"""Dataset API routes."""
import os
import uuid
import tempfile
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from minio import Minio

from app.api.dependencies import get_db, get_minio
from app.models import Dataset, OctreeProcessRequest
from app.repositories import DatasetRepository, OctreeNodeRepository
from app.core.minio_client import BUCKET_RAW, BUCKET_PROCESSED, download_file as minio_download_file
from app.services.pdal_processor import PDALProcessor, PDALPipelineError
from app.services.las_tools_processor import LasToolsProcessor, LasToolsError
from app.services.octree_builder import OctreeBuilder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lidar", tags=["datasets"])


@router.post("/upload")
async def upload_lidar(
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio)
) -> dict:
    """Upload a LiDAR file (LAS/LAZ) to storage."""
    from pathlib import Path
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".las", ".laz"):
        raise HTTPException(status_code=400, detail="Only .las or .laz files are allowed")

    dataset_repo = DatasetRepository(db)
    dataset_id = str(uuid.uuid4())[:8]
    object_name = f"{dataset_id}/{file.filename}"

    try:
        minio_client.put_object(
            BUCKET_RAW,
            object_name,
            file.file,
            length=-1,
            content_type="application/octet-stream",
            part_size=10 * 1024 * 1024,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    stat = minio_client.stat_object(BUCKET_RAW, object_name)
    dataset = await dataset_repo.create(
        filename=file.filename,
        object_name=object_name,
        size=stat.size
    )

    return {
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "object_name": dataset.object_name,
        "size": dataset.size,
        "status": dataset.status,
        "message": "LAZ file uploaded to raw storage"
    }


@router.post("/process/{dataset_id}")
async def process_lidar(
    dataset_id: str,
    request: OctreeProcessRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio)
) -> dict:
    """Start octree processing for a dataset."""
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get(dataset_id)

    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    if dataset.status == "processing":
        raise HTTPException(status_code=400, detail="Dataset is already being processed")

    if dataset.status == "completed":
        raise HTTPException(status_code=400, detail="Dataset already processed")

    await dataset_repo.update_status(dataset_id, "processing")

    background_tasks.add_task(
        _process_octree_background,
        dataset_id, dataset.object_name,
        request.max_depth, request.point_threshold,
        db, minio_client
    )

    return {
        "dataset_id": dataset_id,
        "status": "processing_started",
        "message": f"Octree building started for {dataset.object_name}"
    }


async def _process_octree_background(
    dataset_id: str,
    object_name: str,
    max_depth: int,
    point_threshold: int,
    db: AsyncIOMotorDatabase,
    minio_client: Minio
):
    """Background task for octree processing."""
    dataset_repo = DatasetRepository(db)
    node_repo = OctreeNodeRepository(db)

    try:
        builder = OctreeBuilder(
            minio_client=minio_client,
            dataset_id=dataset_id,
            max_depth=max_depth,
            point_threshold=point_threshold
        )

        nodes = builder.build_octree(object_name, input_in_minio=True, source_bucket=BUCKET_RAW)
        stats = builder.get_stats()

        await node_repo.create_many(dataset_id, nodes)
        await dataset_repo.update_status(
            dataset_id,
            "completed",
            point_count=stats["total_points"],
            node_count=stats["total_nodes"]
        )

        builder.cleanup()

    except Exception as e:
        logger.error(f"Octree processing failed: {e}")
        await dataset_repo.update_status(dataset_id, "failed", error=str(e))


@router.get("/datasets")
async def list_datasets(
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """List all datasets."""
    dataset_repo = DatasetRepository(db)
    datasets = await dataset_repo.list_all()
    return {
        "datasets": [d.model_dump() for d in datasets]
    }


@router.get("/datasets/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """Get dataset details."""
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get(dataset_id)

    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    return dataset.model_dump()


@router.get("/datasets/{dataset_id}/nodes")
async def list_dataset_nodes(
    dataset_id: str,
    depth: Optional[int] = None,
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """Get octree nodes for a dataset."""
    dataset_repo = DatasetRepository(db)
    node_repo = OctreeNodeRepository(db)

    dataset = await dataset_repo.get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    if dataset.status != "completed":
        raise HTTPException(status_code=400, detail=f"Dataset status: {dataset.status}")

    nodes = await node_repo.get_by_dataset(dataset_id, depth)

    return {
        "dataset_id": dataset_id,
        "total_nodes": len(nodes),
        "nodes": nodes
    }


@router.get("/datasets/{dataset_id}/info")
async def get_lidar_info(
    dataset_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio)
) -> dict:
    """Get LiDAR file info using PDAL (with LasTools fallback)."""
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get(dataset_id)

    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    with tempfile.NamedTemporaryFile(suffix=".laz", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        minio_download_file(minio_client, BUCKET_RAW, dataset.object_name, tmp_path)

        # Try PDAL first
        processor = PDALProcessor()
        if processor.use_pdal:
            try:
                info = processor.get_info(tmp_path)
                info["backend"] = "pdal"
                return info
            except PDALPipelineError as e:
                logger.warning(f"PDAL failed, falling back to LAStools: {e}")

        # Fallback to LAStools
        lastools = LasToolsProcessor()
        info = lastools.get_info(tmp_path)
        info["backend"] = "lastools"
        return info

    except (LasToolsError, PDALPipelineError) as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
