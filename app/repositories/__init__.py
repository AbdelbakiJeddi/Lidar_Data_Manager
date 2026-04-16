"""Repository layer for MongoDB database operations."""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models import Dataset, OctreeNode, OctreeNodeDocument


class DatasetRepository:
    """Repository for dataset operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.datasets

    async def create(self, filename: str, object_name: str, size: int) -> Dataset:
        """Create a new dataset record."""
        dataset = Dataset(
            id=str(uuid.uuid4())[:8],
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


class OctreeNodeRepository:
    """Repository for octree node operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.octree_nodes

    async def create(self, dataset_id: str, node: OctreeNode) -> None:
        """Create a single node record."""
        doc = OctreeNodeDocument(
            dataset_id=dataset_id,
            node_id=node.node_id,
            parent_id=node.parent,
            depth=node.depth,
            point_count=node.point_count,
            bbox=node.bbox,
            minio_path=node.minio_path,
            children=node.children
        )
        await self.collection.insert_one(doc.to_mongo())

    async def create_many(self, dataset_id: str, nodes: List[OctreeNode]) -> None:
        """Create multiple node records."""
        if not nodes:
            return
        docs = []
        for n in nodes:
            doc = OctreeNodeDocument(
                dataset_id=dataset_id,
                node_id=n.node_id,
                parent_id=n.parent,
                depth=n.depth,
                point_count=n.point_count,
                bbox=n.bbox,
                minio_path=n.minio_path,
                children=n.children
            )
            docs.append(doc.to_mongo())
        await self.collection.insert_many(docs)

    async def get_by_dataset(self, dataset_id: str, depth: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get nodes by dataset ID with optional depth filter."""
        query = {"dataset_id": dataset_id}
        if depth is not None:
            query["depth"] = depth
        cursor = self.collection.find(query).sort("depth", 1)
        return [doc async for doc in cursor]

    async def get_node(self, dataset_id: str, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific node by dataset and node ID."""
        return await self.collection.find_one({"dataset_id": dataset_id, "node_id": node_id})
