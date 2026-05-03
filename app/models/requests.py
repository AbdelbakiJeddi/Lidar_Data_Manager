"""Request model definitions."""

from pydantic import BaseModel


class TileProcessRequest(BaseModel):
    """Request model for 2D tiling and COPC conversion."""

    tile_size: float = 500.0
