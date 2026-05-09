"""Tile API routes for 2D tile operations."""
import logging
import os
import shutil
import tempfile

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, FileResponse, RedirectResponse
from starlette.datastructures import Headers
from starlette.responses import Response
from datetime import timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from minio import Minio

from app.api.dependencies import get_db, get_minio
from app.repositories import DatasetRepository, TileRepository
from app.core.minio_client import BUCKET_PROCESSED, download_file
from app.services.pdal_processor import PDALProcessor
from app.models import Dataset, BBoxRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lidar/tiles", tags=["tiles"])


# --------------------------------------------------------------------------- #
#  Existing tile lookup routes (unchanged)
# --------------------------------------------------------------------------- #

@router.get("/{dataset_id}/{grid_x}/{grid_y}")
async def get_tile_info(
    dataset_id: str,
    grid_x: int,
    grid_y: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Get tile metadata by grid index."""
    tile_repo = TileRepository(db)

    tile = await tile_repo.get_by_grid_index(dataset_id, grid_x, grid_y)
    if not tile:
        raise HTTPException(status_code=404, detail="Tile not found")

    return tile


@router.get("/{dataset_id}/{grid_x}/{grid_y}/download")
async def download_tile(
    dataset_id: str,
    grid_x: int,
    grid_y: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio),
) -> StreamingResponse:
    """Download a specific tile file."""
    tile_repo = TileRepository(db)

    tile = await tile_repo.get_by_grid_index(dataset_id, grid_x, grid_y)
    if not tile:
        raise HTTPException(status_code=404, detail="Tile not found")

    try:
        response = minio_client.get_object(BUCKET_PROCESSED, tile["minio_path"])
        return StreamingResponse(
            response,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename=tile_{grid_x}_{grid_y}.copc.laz"
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.api_route("/{dataset_id}/{grid_x}/{grid_y}/file{extension:path}", methods=["GET", "HEAD"])
async def get_tile_file(
    dataset_id: str,
    grid_x: int,
    grid_y: int,
    extension: str = "",
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio),
) -> RedirectResponse:
    """Redirect to MinIO presigned URL for direct file access (handles range requests natively)."""
    tile_repo = TileRepository(db)

    tile = await tile_repo.get_by_grid_index(dataset_id, grid_x, grid_y)
    if not tile:
        raise HTTPException(status_code=404, detail="Tile not found")

    public_client = Minio(
        "localhost:9000",
        access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
        secure=False,
        region="us-east-1"
    )
    url = public_client.presigned_get_object(
        BUCKET_PROCESSED,
        tile["minio_path"],
        expires=timedelta(hours=1)
    )
    return RedirectResponse(url)


def _range_iterator(file_path: str, range_header: str, file_size: int):
    """Handle range requests for HTTP 206 responses."""
    import re
    match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not match:
        return
    
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else file_size - 1
    
    with open(file_path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk_size = min(8 * 1024 * 1024, remaining)
            chunk = f.read(chunk_size)
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


# --------------------------------------------------------------------------- #
#  Zone extraction  (rectangle only, multi-dataset)
# --------------------------------------------------------------------------- #

@router.post("/extract-zone")
async def extract_zone(
    request: BBoxRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio),
) -> StreamingResponse:
    """
    Extract and download merged point cloud cropped to a WGS84 rectangle.

    Automatically finds all completed datasets that overlap the requested
    bounding box, reprojects to each dataset's native SRS, crops the
    relevant tiles, and merges everything into a single LAZ file.
    """
    # --- 1. Validate --------------------------------------------------------
    if request.min_lon >= request.max_lon or request.min_lat >= request.max_lat:
        raise HTTPException(status_code=400, detail="Invalid bbox: min must be < max")

    # --- 2. Find overlapping completed datasets -----------------------------
    query = {
        "status": "completed",
        "geographic_bbox.max_x": {"$gt": request.min_lon},
        "geographic_bbox.min_x": {"$lt": request.max_lon},
        "geographic_bbox.max_y": {"$gt": request.min_lat},
        "geographic_bbox.min_y": {"$lt": request.max_lat},
    }
    cursor = db.datasets.find(query)
    dataset_docs = [doc async for doc in cursor]

    if not dataset_docs:
        raise HTTPException(
            status_code=404,
            detail="No completed datasets overlap the selected area",
        )

    logger.info("Zone extraction: %d overlapping datasets found", len(dataset_docs))

    # --- 3. Prepare PDAL & temp dir -----------------------------------------
    pdal = PDALProcessor(require_available=False)
    if not pdal.pdal_version:
        raise HTTPException(status_code=503, detail="PDAL not available")

    tile_repo = TileRepository(db)
    temp_dir = tempfile.mkdtemp(prefix="zone_extract_")

    try:
        from pyproj import Transformer

        dataset_merged_files = []

        for doc in dataset_docs:
            ds = Dataset.from_mongo(doc)
            if not ds.srs_wkt:
                logger.warning("Dataset %s has no SRS, skipping", ds.id)
                continue

            # --- 3a. Reproject WGS84 bbox → native SRS ----------------------
            try:
                transformer = Transformer.from_crs(
                    "EPSG:4326", ds.srs_wkt, always_xy=True
                )
                corners_lon = [request.min_lon, request.min_lon, request.max_lon, request.max_lon]
                corners_lat = [request.min_lat, request.max_lat, request.min_lat, request.max_lat]
                xs, ys = transformer.transform(corners_lon, corners_lat)
                native_min_x, native_max_x = min(xs), max(xs)
                native_min_y, native_max_y = min(ys), max(ys)
            except Exception as e:
                logger.error("Reprojection failed for dataset %s: %s", ds.id, e)
                raise HTTPException(
                    status_code=500,
                    detail=f"Coordinate reprojection failed for dataset {ds.dataset_name}: {e}",
                )

            # --- 3b. Build native-SRS crop rectangle WKT --------------------
            crop_wkt = (
                f"POLYGON(("
                f"{native_min_x} {native_min_y}, "
                f"{native_max_x} {native_min_y}, "
                f"{native_max_x} {native_max_y}, "
                f"{native_min_x} {native_max_y}, "
                f"{native_min_x} {native_min_y}))"
            )

            # --- 3c. Query overlapping tiles ---------------------------------
            tiles = await tile_repo.get_tiles_in_bbox(
                ds.id, native_min_x, native_min_y, native_max_x, native_max_y
            )
            if not tiles:
                logger.info("Dataset %s: no tiles in bbox", ds.id)
                continue

            logger.info("Dataset %s: %d tiles overlap", ds.id, len(tiles))

            # --- 3d. Download + crop each tile --------------------------------
            ds_dir = os.path.join(temp_dir, ds.id)
            os.makedirs(ds_dir, exist_ok=True)
            cropped_paths = []

            for i, tile in enumerate(tiles):
                m_path = tile.get("minio_path")
                if not m_path:
                    continue

                local_path = os.path.join(ds_dir, f"tile_{i}.copc.laz")
                download_file(minio_client, BUCKET_PROCESSED, m_path, local_path)

                cropped_path = os.path.join(ds_dir, f"cropped_{i}.laz")
                pdal.crop_to_polygon(
                    local_path, cropped_path, crop_wkt,
                    request.min_z, request.max_z,
                )

                # Skip empty results
                try:
                    info = pdal.get_info(cropped_path)
                    if info.get("point_count", 0) > 0:
                        cropped_paths.append(cropped_path)
                except Exception:
                    logger.debug("Cropped tile %d empty or unreadable, skipping", i)

            if not cropped_paths:
                continue

            # --- 3e. Merge this dataset's tiles --------------------------------
            ds_merged = os.path.join(ds_dir, "merged.laz")
            if len(cropped_paths) == 1:
                shutil.copy(cropped_paths[0], ds_merged)
            else:
                pdal.merge_files(cropped_paths, ds_merged)
            dataset_merged_files.append(ds_merged)

        # --- 4. Merge across datasets ----------------------------------------
        if not dataset_merged_files:
            raise HTTPException(
                status_code=404,
                detail="No point cloud data found in the selected area",
            )

        final_path = os.path.join(temp_dir, "zone_extraction.laz")
        if len(dataset_merged_files) == 1:
            shutil.copy(dataset_merged_files[0], final_path)
        else:
            pdal.merge_files(dataset_merged_files, final_path)

        # --- 5. Stream response (don't load into memory) ---------------------
        file_size = os.path.getsize(final_path)

        def file_iterator():
            with open(final_path, "rb") as f:
                while chunk := f.read(8 * 1024 * 1024):  # 8 MB chunks
                    yield chunk

        def cleanup():
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

        background_tasks.add_task(cleanup)

        return StreamingResponse(
            file_iterator(),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": "attachment; filename=zone_extraction.laz",
                "Content-Length": str(file_size),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Zone extraction failed: %s", e, exc_info=True)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crop-preview")
async def crop_preview(
    request: BBoxRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio),
):
    """Crop zone to bbox and return a presigned URL for Potree to load."""
    import uuid, tempfile, os as _os
    from pyproj import Transformer

    pdal = PDALProcessor(require_available=False)
    if not pdal.pdal_version:
        raise HTTPException(status_code=503, detail="PDAL not available")

    tile_repo = TileRepository(db)
    temp_dir = tempfile.mkdtemp(prefix="preview_")

    # Clean up old previews
    try:
        old_objects = minio_client.list_objects(BUCKET_PROCESSED, prefix="previews/")
        for obj in old_objects:
            minio_client.remove_object(BUCKET_PROCESSED, obj.object_name)
    except Exception as e:
        logger.warning("Failed to clean up old previews: %s", e)

    try:
        query = {
            "status": "completed",
            "geographic_bbox.max_x": {"$gt": request.min_lon},
            "geographic_bbox.min_x": {"$lt": request.max_lon},
            "geographic_bbox.max_y": {"$gt": request.min_lat},
            "geographic_bbox.min_y": {"$lt": request.max_lat},
        }
        dataset_docs = [doc async for doc in db.datasets.find(query)]
        if not dataset_docs:
            raise HTTPException(status_code=404, detail="No datasets found in area")

        from app.models import Dataset
        cropped_files = []

        for doc in dataset_docs:
            ds = Dataset.from_mongo(doc)
            if not ds.srs_wkt:
                continue

            transformer = Transformer.from_crs("EPSG:4326", ds.srs_wkt, always_xy=True)
            corners_lon = [request.min_lon, request.min_lon, request.max_lon, request.max_lon]
            corners_lat = [request.min_lat, request.max_lat, request.min_lat, request.max_lat]
            xs, ys = transformer.transform(corners_lon, corners_lat)
            native_min_x, native_max_x = min(xs), max(xs)
            native_min_y, native_max_y = min(ys), max(ys)

            crop_wkt = (
                f"POLYGON(("
                f"{native_min_x} {native_min_y}, "
                f"{native_max_x} {native_min_y}, "
                f"{native_max_x} {native_max_y}, "
                f"{native_min_x} {native_max_y}, "
                f"{native_min_x} {native_min_y}))"
            )

            tiles = await tile_repo.get_tiles_in_bbox(
                ds.id, native_min_x, native_min_y, native_max_x, native_max_y
            )
            if not tiles:
                continue

            for i, tile in enumerate(tiles):
                local_path = _os.path.join(temp_dir, f"tile_{i}.copc.laz")
                download_file(minio_client, BUCKET_PROCESSED, tile["minio_path"], local_path)
                cropped_path = _os.path.join(temp_dir, f"cropped_{i}.laz")
                pdal.crop_to_polygon(local_path, cropped_path, crop_wkt, request.min_z, request.max_z)
                try:
                    info = pdal.get_info(cropped_path)
                    if info.get("point_count", 0) > 0:
                        cropped_files.append(cropped_path)
                except Exception:
                    pass

        if not cropped_files:
            raise HTTPException(status_code=404, detail="No points in selected area")

        merged_path = _os.path.join(temp_dir, "preview.laz")
        if len(cropped_files) == 1:
            shutil.copy(cropped_files[0], merged_path)
        else:
            pdal.merge_files(cropped_files, merged_path)

        final_path = _os.path.join(temp_dir, "preview.copc.laz")
        pdal.convert_to_copc(merged_path, final_path)

        preview_key = f"previews/{uuid.uuid4()}.copc.laz"
        minio_client.fput_object(BUCKET_PROCESSED, preview_key, final_path)

        public_client = Minio(
            "localhost:9000",
            access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
            secure=False,
            region="us-east-1"
        )
        url = public_client.presigned_get_object(
            BUCKET_PROCESSED,
            preview_key,
            expires=timedelta(hours=1)
        )
        return {"url": url}

    finally:
        if _os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
