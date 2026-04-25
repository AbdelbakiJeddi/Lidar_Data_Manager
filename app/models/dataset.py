"""Dataset model definitions."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .bounding_box import BoundingBox


class Dataset(BaseModel):
    """Represents a LiDAR dataset in MongoDB."""

    id: str
    filename: str
    object_name: str
    size: int
    bucket: str = "lidar-raw"
    status: str = "uploaded"  # uploaded, processing, completed, failed
    point_count: Optional[int] = None
    node_count: Optional[int] = None
    bbox: Optional[BoundingBox] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None

    def to_mongo(self) -> Dict[str, Any]:
        """Convert to MongoDB document format."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_mongo(cls, doc: Dict[str, Any]) -> "Dataset":
        """Create Dataset from MongoDB document."""
        if doc is None:
            return None
        return cls(**doc)
