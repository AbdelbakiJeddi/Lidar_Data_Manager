"""Request model definitions."""

from pydantic import BaseModel


class OctreeProcessRequest(BaseModel):
    """Request model for octree processing."""

    max_depth: int = 8
    point_threshold: int = 1_000_000
