from pydantic import BaseModel
from typing import List, Optional

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
        """
        Splits the current bounding box into 8 equal octants.
        The order is:
        0: (min_x, min_y, min_z) to (cx, cy, cz)
        1: (cx, min_y, min_z) to (max_x, cy, cz)
        2: (min_x, cy, min_z) to (cx, max_y, cz)
        3: (cx, cy, min_z) to (max_x, max_y, cz)
        4: (min_x, min_y, cz) to (cx, cy, max_z)
        5: (cx, min_y, cz) to (max_x, cy, max_z)
        6: (min_x, cy, cz) to (cx, max_y, max_z)
        7: (cx, cy, cz) to (max_x, max_y, max_z)
        """
        cx, cy, cz = self.get_center()

        # Define the boundaries for the two halves of each axis
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
