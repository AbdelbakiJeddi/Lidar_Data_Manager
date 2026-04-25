"""Octree node repository implementation."""
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models import OctreeNode, OctreeNodeDocument


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
