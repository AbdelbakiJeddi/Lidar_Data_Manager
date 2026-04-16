"""Pydantic models for the LiDAR Data Manager API."""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Represents a 3D bounding box for a point cloud node."""
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    def get_center(self) -> tuple[float, float, float]:
        """Returns the center point of the bounding box."""
        return (
            (self.min_x + self.max_x) / 2,
            (self.min_y + self.max_y) / 2,
            (self.min_z + self.max_z) / 2
        )

    def split_into_octants(self) -> List["BoundingBox"]:
        """Splits the current bounding box into 8 equal octants."""
        cx, cy, cz = self.get_center()
        x_bounds = [(self.min_x, cx), (cx, self.max_x)]
        y_bounds = [(self.min_y, cy), (cy, self.max_y)]
        z_bounds = [(self.min_z, cz), (cz, self.max_z)]
        octants = []
        for z in range(2):
            for y in range(2):
                for x in range(2):
                    octants.append(BoundingBox(
                        min_x=x_bounds[x][0],
                        min_y=y_bounds[y][0],
                        min_z=z_bounds[z][0],
                        max_x=x_bounds[x][1],
                        max_y=y_bounds[y][1],
                        max_z=z_bounds[z][1]
                    ))
        return octants


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


class OctreeProcessRequest(BaseModel):
    """Request model for octree processing."""
    max_depth: int = 8
    point_threshold: int = 1_000_000
