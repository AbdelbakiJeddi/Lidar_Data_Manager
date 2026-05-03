"""Tile model for flat 2D grid."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from .bounding_box import BoundingBox


class Tile(BaseModel):
    """Represents a single COPC tile in the 2D grid."""

    id: Optional[str] = None
    dataset_id: str
    grid_index: List[int]  # [x, y]
    bbox: BoundingBox
    point_count: int
    minio_path: str
    file_size_bytes: int

    def to_mongo(self) -> Dict[str, Any]:
        """Convert to MongoDB document format."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_mongo(cls, doc: Dict[str, Any]) -> "Tile":
        """Create Tile from MongoDB document."""
        if doc is None:
            return None
        if "_id" in doc:
            doc["id"] = str(doc.pop("_id"))
        return cls(**doc)
