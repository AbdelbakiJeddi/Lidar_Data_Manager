"""Request model definitions."""

from pydantic import BaseModel, Field


class TileProcessRequest(BaseModel):
    """Request model for tile processing."""

    tile_size_meters: float = Field(default=2000.0, gt=0)


class BBoxRequest(BaseModel):
    """Rectangular zone selection in WGS84 (lon/lat)."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    min_z: float = -1e10
    max_z: float = 1e10
