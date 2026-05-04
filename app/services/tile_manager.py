"""TileManager service for orchestrating 2D tiling and COPC conversion."""

import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from minio import Minio
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models import BoundingBox, Dataset, Tile
from app.core.minio_client import BUCKET_PROCESSED, BUCKET_RAW, download_file, upload_local_file
from app.services.pdal_processor import PDALProcessor

logger = logging.getLogger(__name__)


class TileManager:
    """Manages the 2D tiling and COPC conversion workflow.
    
    Bases on: copc_tiling_plan.md
    """

    def __init__(self, minio_client: Minio, db: AsyncIOMotorDatabase):
        self.minio_client = minio_client
        self.db = db
        self.pdal = PDALProcessor()

    async def process_dataset(self, dataset_id: str, tile_size: float = 2000.0):
        """Execute the full split -> convert -> upload -> index workflow.
        
        This follows the 'Flat 2D Tiling' approach.
        """
        logger.info(f"Starting tiling process for dataset {dataset_id}")

        # 1. Get Dataset metadata
        doc = await self.db.datasets.find_one({"id": dataset_id})
        if not doc:
            raise ValueError(f"Dataset {dataset_id} not found")

        dataset = Dataset.from_mongo(doc)
        
        # Update status to processing
        await self.db.datasets.update_one(
            {"id": dataset_id}, 
            {"$set": {"status": "processing", "updated_at": datetime.now(timezone.utc)}}
        )

        temp_dir = tempfile.mkdtemp(prefix=f"tiling_{dataset_id}_")

        try:
            # 2. Download source
            local_input = os.path.join(temp_dir, "source.laz")
            download_file(self.minio_client, BUCKET_RAW, dataset.object_name, local_input)
            logger.info(f"Downloaded source file to {local_input}")

            # 3. Split to grid
            raw_tiles_dir = os.path.join(temp_dir, "raw_tiles")
            os.makedirs(raw_tiles_dir, exist_ok=True)

            # Alignment origin (use min_x, min_y of dataset for tight grid)
            info = self.pdal.get_info(local_input)
            bbox_dict = info.get("bbox")
            if not bbox_dict:
                raise ValueError("Dataset bbox unavailable for tiling")

            origin_x = bbox_dict["min_x"]
            origin_y = bbox_dict["min_y"]

            logger.info(f"Splitting into {tile_size}m tiles with origin ({origin_x}, {origin_y})")
            raw_tile_paths = self.pdal.split_to_grid(
                local_input, raw_tiles_dir, tile_size, origin_x=origin_x, origin_y=origin_y
            )

            tiles_metadata = []
            for i, raw_tile in enumerate(raw_tile_paths):
                # 4. Get individual tile info
                info = self.pdal.get_info(raw_tile)
                bbox_dict = info["bbox"]
                point_count = info["point_count"]

                if point_count == 0:
                    continue

                # Calculate grid indices [x, y]
                # We use the center of the tile to avoid floating point edge issues
                center_x = (bbox_dict["min_x"] + bbox_dict["max_x"]) / 2
                center_y = (bbox_dict["min_y"] + bbox_dict["max_y"]) / 2
                grid_x = int((center_x - origin_x) // tile_size)
                grid_y = int((center_y - origin_y) // tile_size)

                # 5. Convert to COPC
                copc_file = raw_tile.replace(".laz", ".copc.laz")
                logger.debug(f"Converting tile {i} to COPC: {copc_file}")
                self.pdal.convert_to_copc(raw_tile, copc_file)

                # 6. Upload to MinIO
                object_name = f"datasets/{dataset_id}/tiles/tile_{grid_x}_{grid_y}.copc.laz"
                upload_local_file(self.minio_client, BUCKET_PROCESSED, copc_file, object_name)

                # 7. Create Tile model
                tile = Tile(
                    dataset_id=dataset_id,
                    grid_x=grid_x,
                    grid_y=grid_y,
                    bbox=BoundingBox(**bbox_dict),
                    point_count=point_count,
                    minio_path=object_name,
                    file_size_bytes=os.path.getsize(copc_file),
                )
                tiles_metadata.append(tile.to_mongo())

            # 8. Save all tiles to MongoDB
            if tiles_metadata:
                # Delete any existing tiles for this dataset (idempotency)
                await self.db.tiles.delete_many({"dataset_id": dataset_id})
                await self.db.tiles.insert_many(tiles_metadata)

            # 9. Update Dataset status
            await self.db.datasets.update_one(
                {"id": dataset_id},
                {
                    "$set": {
                        "status": "completed",
                        "tiling_strategy": "flat_2d_grid",
                        "grid_origin": [origin_x, origin_y],
                        "tile_size_meters": tile_size,
                        "total_tiles": len(tiles_metadata),
                        "point_count": info.get("point_count"),
                        "bbox": bbox_dict,
                        "processed_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            logger.info(f"Dataset {dataset_id} processing completed. {len(tiles_metadata)} tiles generated.")

        except Exception as e:
            logger.error(f"Failed to process dataset {dataset_id}: {e}", exc_info=True)
            await self.db.datasets.update_one(
                {"id": dataset_id},
                {
                    "$set": {
                        "status": "failed",
                        "error": str(e),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            raise
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
