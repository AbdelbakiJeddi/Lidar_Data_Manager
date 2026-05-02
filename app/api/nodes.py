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


from pydantic import BaseModel
from typing import List, Tuple

class PolygonZoneRequest(BaseModel):
    """Request body for polygon-based zone extraction."""
    coordinates: List[List[float]]  # [[lon, lat], [lon, lat], ...]
    min_z: float = -1e10
    max_z: float = 1e10


@router.post("/{dataset_id}/zone")
async def download_zone(
    dataset_id: str,
    request: PolygonZoneRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio)
) -> Response:
    """
    Download merged point cloud cropped to an arbitrary polygon.
    
    Coordinates are provided as [[lon, lat], ...] in geographic (WGS84).
    They are automatically reprojected to the dataset's native SRS.
    """
    node_repo = OctreeNodeRepository(db)
    dataset_repo = DatasetRepository(db)

    dataset = await dataset_repo.get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

    if len(request.coordinates) < 3:
        raise HTTPException(status_code=400, detail="Polygon requires at least 3 points")

    # Ensure polygon is closed
    coords = list(request.coordinates)
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    # Reproject coordinates from WGS84 to native SRS if needed
    native_coords = coords
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    is_geographic = all(abs(x) <= 180 for x in lons) and all(abs(y) <= 90 for y in lats)

    if is_geographic and dataset.srs_wkt:
        try:
            from pyproj import Transformer
            transformer = Transformer.from_crs("EPSG:4326", dataset.srs_wkt, always_xy=True)
            native_coords = []
            for lon, lat in coords:
                x, y = transformer.transform(lon, lat)
                native_coords.append([x, y])
            logger.info(f"Reprojected {len(coords)} polygon vertices to native SRS")
        except Exception as e:
            logger.warning(f"Coordinate reprojection failed: {e}")

    # Build WKT POLYGON from native coordinates
    wkt_coords = ", ".join(f"{c[0]} {c[1]}" for c in native_coords)
    wkt_polygon = f"POLYGON(({wkt_coords}))"

    # Compute bounding box of native polygon for node intersection query
    xs = [c[0] for c in native_coords]
    ys = [c[1] for c in native_coords]
    poly_bbox = BoundingBox(
        min_x=min(xs), min_y=min(ys), min_z=request.min_z,
        max_x=max(xs), max_y=max(ys), max_z=request.max_z
    )

    nodes = await node_repo.get_nodes_in_bbox(dataset_id, poly_bbox)
    if not nodes:
        raise HTTPException(status_code=404, detail="No nodes found in specified zone")

    pdal = PDALProcessor(require_available=False)
    if not pdal.pdal_version:
        raise HTTPException(status_code=503, detail="PDAL not available")

    temp_dir = tempfile.mkdtemp(prefix="zone_")
    downloaded_files = []
    cropped_files = []

    try:
        for node in nodes:
            local_path = os.path.join(temp_dir, f"node_{node['node_id']}.laz")
            download_file(minio_client, BUCKET_PROCESSED, node["minio_path"], local_path)
            downloaded_files.append(local_path)

        for i, local_path in enumerate(downloaded_files):
            cropped_path = os.path.join(temp_dir, f"cropped_{i}.laz")
            pdal.crop_to_polygon(local_path, cropped_path, wkt_polygon, request.min_z, request.max_z)
            cropped_files.append(cropped_path)

        merged_path = os.path.join(temp_dir, "merged.laz")
        pdal.merge_files(cropped_files, merged_path)

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
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
