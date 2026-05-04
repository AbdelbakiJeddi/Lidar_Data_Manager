"""Dataset model definitions."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .bounding_box import BoundingBox


class Dataset(BaseModel):
    """Represents a tracked MinIO object stored in MongoDB."""

    id: str
    dataset_name: str
    filename: str
    object_name: str
    size: int
    bucket: str = "lidar-raw"
    content_type: Optional[str] = None
    etag: Optional[str] = None
    last_modified: Optional[datetime] = None
    status: str = "uploaded"  # uploaded, processing, completed, failed
    point_count: Optional[int] = None
    tiling_strategy: Optional[str] = None
    grid_origin: Optional[list[float]] = None
    tile_size_meters: Optional[float] = None
    total_tiles: Optional[int] = None
    bbox: Optional[BoundingBox] = None
    geographic_bbox: Optional[BoundingBox] = None
    geographic_boundary: Optional[Dict[str, Any]] = None
    srs_wkt: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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
