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
