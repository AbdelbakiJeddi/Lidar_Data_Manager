"""Request model definitions."""

from typing import List, Optional
from pydantic import BaseModel


class TileProcessRequest(BaseModel):
    """Request model for 2D tiling and COPC conversion."""

    tile_size: float = 500.0


class ZoneCropRequest(BaseModel):
    """Request model for rectangular zone extraction."""
    
    dataset_id: str
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    min_z: float = -1e10
    max_z: float = 1e10


class MultiZoneCropRequest(BaseModel):
    """Request model for multi-dataset rectangular zone extraction."""
    
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    min_z: float = -1e10
    max_z: float = 1e10
    dataset_ids: Optional[List[str]] = None  # If None, extract from all datasets
