"""Dataset API routes."""
import os
import uuid
import tempfile
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, BackgroundTasks, Depends, Body
from fastapi.responses import StreamingResponse, JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from minio import Minio
from minio.error import S3Error

from app.api.dependencies import get_db, get_minio
from app.models import Dataset, TileProcessRequest, BoundingBox, ZoneCropRequest, MultiZoneCropRequest
from app.repositories import DatasetRepository, TileRepository
from app.core.minio_client import BUCKET_RAW, BUCKET_PROCESSED, download_file as minio_download_file, upload_local_file
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


@router.post("/datasets/{dataset_id}/crop")
async def crop_zone(
    dataset_id: str,
    request: ZoneCropRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio)
) -> StreamingResponse:
    """Crop a single dataset to a rectangular bounding box and return LAZ file."""
    dataset_repo = DatasetRepository(db)
    tile_repo = TileRepository(db)
    
    dataset = await dataset_repo.get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    
    # Get tiles that intersect with the crop bbox
    tiles = await tile_repo.get_tiles_in_bbox(
        dataset_id, 
        request.min_x, request.min_y, 
        request.max_x, request.max_y
    )
    
    if not tiles:
        raise HTTPException(status_code=404, detail="No tiles found in the specified area")
    
    # Download all relevant tiles and merge them
    with tempfile.TemporaryDirectory() as tmpdir:
        tile_paths = []
        for tile in tiles:
            tile_path = os.path.join(tmpdir, f"{tile['tile_key']}.laz")
            object_name = tile['object_name']
            minio_download_file(minio_client, BUCKET_PROCESSED, object_name, tile_path)
            tile_paths.append(tile_path)
        
        # Merge all tiles into one file
        merged_path = os.path.join(tmpdir, "merged.laz")
        processor = PDALProcessor()
        processor.merge_files(tile_paths, merged_path)
        
        # Crop the merged file to the exact bbox
        output_path = os.path.join(tmpdir, "cropped.laz")
        bbox = BoundingBox(
            min_x=request.min_x,
            min_y=request.min_y,
            min_z=request.min_z,
            max_x=request.max_x,
            max_y=request.max_y,
            max_z=request.max_z
        )
        result = processor.crop_to_bbox(merged_path, output_path, bbox)
        
        # Stream the result back
        def iterfile():
            with open(output_path, "rb") as f:
                yield from f
        
        return StreamingResponse(
            iterfile(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename=zone_{dataset_id}.laz"}
        )


@router.post("/datasets/crop-multi")
async def crop_multi_zone(
    request: MultiZoneCropRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio)
) -> StreamingResponse:
    """Crop multiple datasets to a rectangular bounding box and return merged LAZ file."""
    dataset_repo = DatasetRepository(db)
    tile_repo = TileRepository(db)
    
    # Get all datasets or filter by provided IDs
    if request.dataset_ids:
        datasets = []
        for ds_id in request.dataset_ids:
            ds = await dataset_repo.get(ds_id)
            if ds:
                datasets.append(ds)
    else:
        datasets = await dataset_repo.list_all()
    
    if not datasets:
        raise HTTPException(status_code=404, detail="No datasets found")
    
    # Collect all tiles from all datasets that intersect with the crop bbox
    all_tile_paths = []
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for dataset in datasets:
            tiles = await tile_repo.get_tiles_in_bbox(
                dataset.id, 
                request.min_x, request.min_y, 
                request.max_x, request.max_y
            )
            
            if not tiles:
                continue
            
            # Download and merge tiles for this dataset
            tile_paths = []
            for tile in tiles:
                tile_path = os.path.join(tmpdir, f"{dataset.id}_{tile['tile_key']}.laz")
                object_name = tile['object_name']
                minio_download_file(minio_client, BUCKET_PROCESSED, object_name, tile_path)
                tile_paths.append(tile_path)
            
            if tile_paths:
                # Merge tiles for this dataset
                dataset_merged_path = os.path.join(tmpdir, f"merged_{dataset.id}.laz")
                processor = PDALProcessor()
                processor.merge_files(tile_paths, dataset_merged_path)
                
                # Crop to bbox
                cropped_path = os.path.join(tmpdir, f"cropped_{dataset.id}.laz")
                bbox = BoundingBox(
                    min_x=request.min_x,
                    min_y=request.min_y,
                    min_z=request.min_z,
                    max_x=request.max_x,
                    max_y=request.max_y,
                    max_z=request.max_z
                )
                processor.crop_to_bbox(dataset_merged_path, cropped_path, bbox)
                all_tile_paths.append(cropped_path)
        
        if not all_tile_paths:
            raise HTTPException(status_code=404, detail="No data found in the specified area")
        
        # Merge all cropped datasets into one final file
        final_output = os.path.join(tmpdir, "final_merged.laz")
        processor = PDALProcessor()
        processor.merge_files(all_tile_paths, final_output)
        
        # Stream the result back
        def iterfile():
            with open(final_output, "rb") as f:
                yield from f
        
        return StreamingResponse(
            iterfile(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=multi_zone_extraction.laz"}
        )