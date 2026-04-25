"""Dataset repository implementation."""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models import Dataset


class DatasetRepository:
    """Repository for dataset operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.datasets

    async def create(self, dataset_name: str, filename: str, object_name: str, size: int) -> Dataset:
        """Create a new dataset record."""
        dataset = Dataset(
            id=str(uuid.uuid4())[:8],
            dataset_name=dataset_name,
            filename=filename,
            object_name=object_name,
            size=size,
            status="uploaded",
            created_at=datetime.utcnow()
        )
        await self.collection.insert_one(dataset.to_mongo())
        return dataset

    async def get(self, dataset_id: str) -> Optional[Dataset]:
        """Get dataset by ID."""
        doc = await self.collection.find_one({"id": dataset_id})
        return Dataset.from_mongo(doc) if doc else None

    async def get_by_object_name(self, object_name: str) -> Optional[Dataset]:
        """Get dataset by object name."""
        doc = await self.collection.find_one({"object_name": object_name})
        return Dataset.from_mongo(doc) if doc else None

    async def get_by_dataset_name(self, dataset_name: str) -> List[Dataset]:
        """Get all datasets (files) belonging to a specific dataset group."""
        cursor = self.collection.find({"dataset_name": dataset_name}).sort("created_at", -1)
        return [Dataset.from_mongo(doc) async for doc in cursor]

    async def list_unique_datasets(self) -> List[str]:
        """List all unique dataset names (groups) in the system."""
        return await self.collection.distinct("dataset_name")

    async def update_status(
        self,
        dataset_id: str,
        status: str,
        point_count: Optional[int] = None,
        node_count: Optional[int] = None,
        error: Optional[str] = None
    ) -> None:
        """Update dataset status and optional fields."""
        update = {
            "status": status,
            "updated_at": datetime.utcnow(),
            "processed_at": datetime.utcnow() if status in ["completed", "failed"] else None
        }
        if point_count is not None:
            update["point_count"] = point_count
        if node_count is not None:
            update["node_count"] = node_count
        if error is not None:
            update["error"] = error
        await self.collection.update_one({"id": dataset_id}, {"$set": update})

    async def list_all(self) -> List[Dataset]:
        """List all datasets ordered by creation date."""
        cursor = self.collection.find().sort("created_at", -1)
        return [Dataset.from_mongo(doc) async for doc in cursor]
