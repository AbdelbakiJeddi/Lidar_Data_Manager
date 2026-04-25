"""Octree node model definitions."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .bounding_box import BoundingBox


class OctreeNode(BaseModel):
    """Represents a single node (datablock) in the Octree structure."""

    node_id: str
    depth: int
    bbox: BoundingBox
    point_count: int
    is_leaf: bool
    children: List[str] = []
    parent: Optional[str] = None
    minio_path: str


class OctreeNodeDocument(BaseModel):
    """Represents an octree node stored in MongoDB."""

    id: Optional[str] = None
    dataset_id: str
    node_id: str
    parent_id: Optional[str] = None
    depth: int
    point_count: int
    bbox: BoundingBox
    minio_path: str
    children: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_mongo(self) -> Dict[str, Any]:
        """Convert to MongoDB document format."""
        data = self.model_dump(exclude_none=True)
        data.pop("id", None)  # Remove id field for MongoDB
        return data

    @classmethod
    def from_mongo(cls, doc: Dict[str, Any]) -> "OctreeNodeDocument":
        """Create OctreeNodeDocument from MongoDB document."""
        if doc is None:
            return None
        return cls(**doc)
