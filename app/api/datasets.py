"""Dataset API routes."""
import os
import uuid
import tempfile
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from minio import Minio

from app.api.dependencies import get_db, get_minio
from app.models import Dataset, TileProcessRequest
from app.repositories import DatasetRepository, TileRepository
from app.core.minio_client import BUCKET_RAW, BUCKET_PROCESSED, download_file as minio_download_file
from app.services.pdal_processor import PDALProcessor, PDALPipelineError
from app.services.tile_manager import TileManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lidar", tags=["datasets"])


@router.post("/upload")
async def upload_lidar(
    file: UploadFile = File(...),
    dataset_name: str = Form(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio)
) -> dict:
    """Upload a LiDAR file (LAS/LAZ) to storage."""
    from pathlib import Path
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".las", ".laz"):
        raise HTTPException(status_code=400, detail="Only .las or .laz files are allowed")

    dataset_repo = DatasetRepository(db)
    file_id = str(uuid.uuid4())[:8]
    object_name = f"uploads/{dataset_name}/{file_id}/{file.filename}"

    from fastapi.concurrency import run_in_threadpool
    
    try:
        await run_in_threadpool(
            minio_client.put_object,
            BUCKET_RAW,
            object_name,
            file.file,
            length=-1,
            content_type="application/octet-stream",
            part_size=10 * 1024 * 1024,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    stat = await run_in_threadpool(minio_client.stat_object, BUCKET_RAW, object_name)
    dataset = await dataset_repo.create(
        dataset_name=dataset_name,
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
    request: TileProcessRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio)
) -> dict:
    """Start 2D tiling and COPC processing for a dataset."""
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get(dataset_id)

    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    if dataset.status == "processing":
        raise HTTPException(status_code=400, detail="Dataset is already being processed")

    # Update status to processing
    await dataset_repo.update_status(dataset_id, "processing")

    background_tasks.add_task(
        _process_tiling_background,
        dataset_id, 
        request.tile_size,
        db, 
        minio_client
    )

    return {
        "dataset_id": dataset_id,
        "status": "processing_started",
        "message": f"2D tiling and COPC conversion started for {dataset.object_name}"
    }


async def _process_tiling_background(
    dataset_id: str,
    tile_size: float,
    db: AsyncIOMotorDatabase,
    minio_client: Minio
):
    """Background task for flat 2D tiling and COPC conversion."""
    try:
        # Extract metadata first to ensure bbox is populated
        dataset_repo = DatasetRepository(db)
        dataset = await dataset_repo.get(dataset_id)
        
        with tempfile.NamedTemporaryFile(suffix=".laz") as tmp:
            minio_download_file(minio_client, BUCKET_RAW, dataset.object_name, tmp.name)
            pdal_proc = PDALProcessor()
            info = pdal_proc.get_info(tmp.name)
            
            srs_wkt = info.get("srs_wkt")
            geographic_boundary = pdal_proc.get_boundary(tmp.name, srs_wkt)
            
            # Update dataset with geographic bounds so it appears on map immediately
            await dataset_repo.update_status(
                dataset_id,
                "processing",
                bbox=info["bbox"],
                geographic_bbox=info.get("geographic_bbox"),
                geographic_boundary=geographic_boundary,
                srs_wkt=srs_wkt
            )

        # Execute tiling
        manager = TileManager(minio_client, db)
        await manager.process_dataset(dataset_id, tile_size=tile_size)

    except Exception as e:
        logger.error(f"Tiling process failed: {e}", exc_info=True)
        dataset_repo = DatasetRepository(db)
        await dataset_repo.update_status(dataset_id, "failed", error=str(e))


@router.get("/datasets")
async def list_datasets(
    dataset_name: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """List datasets, optionally filtered by group name."""
    dataset_repo = DatasetRepository(db)
    if dataset_name:
        datasets = await dataset_repo.get_by_dataset_name(dataset_name)
    else:
        datasets = await dataset_repo.list_all()
    return {
        "datasets": [d.model_dump() for d in datasets]
    }


@router.get("/dataset-groups")
async def list_dataset_groups(
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """List all unique dataset group names."""
    dataset_repo = DatasetRepository(db)
    groups = await dataset_repo.list_unique_datasets()
    return {
        "groups": groups
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


@router.get("/datasets/{dataset_id}/tiles")
async def list_dataset_tiles(
    dataset_id: str,
    min_x: Optional[float] = None,
    min_y: Optional[float] = None,
    max_x: Optional[float] = None,
    max_y: Optional[float] = None,
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """Get 2D tiles for a dataset, optionally filtered by spatial bounds."""
    dataset_repo = DatasetRepository(db)
    tile_repo = TileRepository(db)

    dataset = await dataset_repo.get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    if all(v is not None for v in [min_x, min_y, max_x, max_y]):
        tiles = await tile_repo.get_tiles_in_bbox(dataset_id, min_x, min_y, max_x, max_y)
    else:
        tiles = await tile_repo.get_by_dataset(dataset_id)

    return {
        "dataset_id": dataset_id,
        "total_tiles": len(tiles),
        "tiles": tiles
    }


@router.get("/datasets/{dataset_id}/info")
async def get_lidar_info(
    dataset_id: str,
    override_srs: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio)
) -> dict:
    """Get LiDAR file info using PDAL."""
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get(dataset_id)

    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    with tempfile.NamedTemporaryFile(suffix=".laz", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        minio_download_file(minio_client, BUCKET_RAW, dataset.object_name, tmp_path)

        processor = PDALProcessor()
        info = processor.get_info(tmp_path, override_srs=override_srs)
        
        # Update dataset record with newly extracted info if missing
        await dataset_repo.update_status(
            dataset_id,
            dataset.status,
            point_count=info["point_count"],
            bbox=info["bbox"],
            geographic_bbox=info["geographic_bbox"],
            srs_wkt=info["srs_wkt"]
        )
        
        info["backend"] = "pdal"
        return info

    except PDALPipelineError as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
