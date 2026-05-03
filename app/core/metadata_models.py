"""Metadata models for LiDAR processing.

Re-exports BoundingBox and Tile from app.models for backward compatibility.
"""

from app.models import BoundingBox, Tile

__all__ = ["BoundingBox", "Tile"]
