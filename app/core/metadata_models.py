"""Metadata models for LiDAR processing.

Re-exports BoundingBox and OctreeNode from app.models for backward compatibility.
"""

from app.models import BoundingBox, OctreeNode

__all__ = ["BoundingBox", "OctreeNode"]
