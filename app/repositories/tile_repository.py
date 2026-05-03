"""Tile repository implementation for flat 2D tiles."""

from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models import Tile


class TileRepository:
    """Repository for 2D tile operations."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.tiles

    async def create_many(self, tiles: List[Tile]) -> None:
        """Create multiple tile records."""
        if not tiles:
            return
        docs = [t.to_mongo() for t in tiles]
        await self.collection.insert_many(docs)

    async def get_by_dataset(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Get all tiles for a dataset."""
        cursor = self.collection.find({"dataset_id": dataset_id}, {"_id": 0})
        return [doc async for doc in cursor]

    async def get_tiles_in_bbox(
        self, dataset_id: str, min_x: float, min_y: float, max_x: float, max_y: float
    ) -> List[Dict[str, Any]]:
        """Spatial query for tiles within a bounding box (2D)."""
        query = {
            "dataset_id": dataset_id,
            "bbox.max_x": {"$gt": min_x},
            "bbox.min_x": {"$lt": max_x},
            "bbox.max_y": {"$gt": min_y},
            "bbox.min_y": {"$lt": max_y},
        }
        cursor = self.collection.find(query, {"_id": 0})
        return [doc async for doc in cursor]

    async def delete_by_dataset(self, dataset_id: str) -> None:
        """Delete all tiles for a dataset."""
        await self.collection.delete_many({"dataset_id": dataset_id})
