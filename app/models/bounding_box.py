"""Bounding box model definitions."""

from typing import List

from pydantic import BaseModel


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
            (self.min_z + self.max_z) / 2,
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
                    octants.append(
                        BoundingBox(
                            min_x=x_bounds[x][0],
                            min_y=y_bounds[y][0],
                            min_z=z_bounds[z][0],
                            max_x=x_bounds[x][1],
                            max_y=y_bounds[y][1],
                            max_z=z_bounds[z][1],
                        )
                    )
        return octants

    def with_margin(self, margin: float = 0.01) -> "BoundingBox":
        """Return a new BoundingBox expanded by *margin* on every face.

        This prevents floating-point exclusion errors when cropping points
        that lie exactly on an octant boundary (SPSLiDAR convention).
        """
        return BoundingBox(
            min_x=self.min_x - margin,
            min_y=self.min_y - margin,
            min_z=self.min_z - margin,
            max_x=self.max_x + margin,
            max_y=self.max_y + margin,
            max_z=self.max_z + margin,
        )

    def intersects(self, other: "BoundingBox") -> bool:
        """Check if this bounding box intersects with another."""
        return not (
            self.max_x <= other.min_x or self.min_x >= other.max_x or
            self.max_y <= other.min_y or self.min_y >= other.max_y or
            self.max_z <= other.min_z or self.min_z >= other.max_z
        )
