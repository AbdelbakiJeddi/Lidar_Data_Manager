import os
import subprocess
import json
import tempfile
import logging
from pathlib import Path
from typing import List, Dict, Optional
from minio import Minio

from app.core.metadata_models import OctreeNode, BoundingBox
from app.core.minio_client import upload_local_file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to LAStools binary directory
# This should be configurable via env or settings, but hardcoded for current env consistency
LASTOOLS_BIN = "/home/abok/lastools/bin"

class LAStoolsWrapper:
    """Wrapper for LAStools CLI commands to perform point cloud operations."""

    @staticmethod
    def get_info(input_file: str) -> Dict:
        """Executes lasinfo to extract bounding box and point count."""
        # We use -json if supported, otherwise we fall back to text parsing
        cmd = [os.path.join(LASTOOLS_BIN, "lasinfo64"), "-i", input_file, "-no_check", "-json"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            # Fallback to text parsing for older versions of lasinfo
            cmd = [os.path.join(LASTOOLS_BIN, "lasinfo64"), "-i", input_file, "-no_check"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return LAStoolsWrapper._parse_info_text(result.stdout + "\n" + result.stderr)

    @staticmethod
    def _parse_info_text(text: str) -> Dict:
        """Parses lasinfo text output to extract basic metadata."""
        info = {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0], "count": 0}
        for line in text.splitlines():
            line = line.lower()
            if "min x y z:" in line:
                parts = line.split(":")[-1].strip().split()
                info["min"] = [float(p) for p in parts]
            if "max x y z:" in line:
                parts = line.split(":")[-1].strip().split()
                info["max"] = [float(p) for p in parts]
            if "number of point records:" in line:
                info["count"] = int(line.split(":")[-1].strip())
        return info

    @staticmethod
    def crop(input_file: str, output_file: str, bbox: BoundingBox):
        """
        Uses las2las to crop points within the specified bounding box.
        SPSLiDAR Logic: las2las -i in.laz -o out.laz -keep_xyz xmin ymin zmin xmax ymax zmax
        """
        cmd = [
            os.path.join(LASTOOLS_BIN, "las2las64"),
            "-i", input_file,
            "-o", output_file,
            "-keep_xyz",
            str(bbox.min_x), str(bbox.min_y), str(bbox.min_z),
            str(bbox.max_x), str(bbox.max_y), str(bbox.max_z)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @staticmethod
    def optimize(input_file: str, output_file: str):
        """Uses lasoptimize to compress and optimize the LAZ file."""
        cmd = [os.path.join(LASTOOLS_BIN, "lasoptimize64"), "-i", input_file, "-o", output_file]
        subprocess.run(cmd, check=True, capture_output=True)

class OctreeProcessor:
    """
    Core engine that implements the SPSLiDAR Octree building algorithm.
    Recursively subdivides a LiDAR dataset and stores chunks in MinIO.
    """
    def __init__(self, minio_client: Minio, bucket: str, max_depth: int = 8, point_threshold: int = 1_000_000):
        self.client = minio_client
        self.bucket = bucket
        self.max_depth = max_depth
        self.point_threshold = point_threshold

    def process_dataset(self, dataset_id: str, root_laz_path: str):
        """
        Main entry point. Downloads the root file, extracts initial bbox,
        and starts the recursive subdivision.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_root = os.path.join(tmp_dir, "root.laz")

            # 1. Download root file from MinIO
            logger.info(f"Downloading root file {root_laz_path} to {local_root}")
            self.client.fget_object(self.bucket, root_laz_path, local_root)

            # 2. Extract root metadata
            info = LAStoolsWrapper.get_info(local_root)
            if "lasinfo" in info: # JSON structure
                header = info["lasinfo"]["header"]
                root_bbox = BoundingBox(
                    min_x=header["min_x"], min_y=header["min_y"], min_z=header["min_z"],
                    max_x=header["max_x"], max_y=header["max_y"], max_z=header["max_z"]
                )
                root_count = info["lasinfo"]["report"]["number_of_points"]
            else: # Fallback structure
                root_bbox = BoundingBox(
                    min_x=info["min"][0], min_y=info["min"][1], min_z=info["min"][2],
                    max_x=info["max"][0], max_y=info["max"][1], max_z=info["max"][2]
                )
                root_count = info["count"]

            # 3. Start recursive splitting
            self._split_recursive(local_root, root_bbox, depth=0, node_id="0", parent_id=None,
                                 dataset_id=dataset_id, tmp_dir=tmp_dir)

    def _split_recursive(self, input_file: str, bbox: BoundingBox, depth: int, node_id: str,
                        parent_id: Optional[str], dataset_id: str, tmp_dir: str):
        """
        Recursively splits the point cloud into 8 octants using the SPSLiDAR logic.
        """
        # Get point count for this node
        info = LAStoolsWrapper.get_info(input_file)
        count = info["lasinfo"]["report"]["number_of_points"] if "lasinfo" in info else info["count"]

        # Base Case: Check if this node should be a leaf
        is_leaf = (depth >= self.max_depth) or (count <= self.point_threshold)

        # MinIO storage paths
        minio_path = f"lidar/datasets/{dataset_id}/octree/depth={depth}/node_{node_id}.laz"
        metadata_path = minio_path.replace(".laz", ".json")

        children_ids = []
        if not is_leaf:
            # Split the current bounding box into 8 octants
            octants = bbox.split_into_octants()

            for i, child_bbox in enumerate(octants):
                child_node_id = f"{node_id}_{i}"
                child_tmp_file = os.path.join(tmp_dir, f"node_{child_node_id}.laz")

                try:
                    # Crop points for this octant
                    LAStoolsWrapper.crop(input_file, child_tmp_file, child_bbox)

                    # Only recurse if the file was actually created and is not empty
                    if os.path.exists(child_tmp_file) and os.path.getsize(child_tmp_file) > 0:
                        children_ids.append(child_node_id)
                        self._split_recursive(child_tmp_file, child_bbox, depth + 1, child_node_id,
                                             node_id, dataset_id, tmp_dir)
                except Exception as e:
                    logger.warning(f"Failed to create octant {i} for node {node_id}: {e}")

        # Optimization: Run lasoptimize on leaf nodes or all nodes if desired
        if is_leaf:
            optimized_tmp = os.path.join(tmp_dir, f"opt_{node_id}.laz")
            LAStoolsWrapper.optimize(input_file, optimized_tmp)
            upload_file = optimized_tmp
        else:
            upload_file = input_file

        # Upload the resulting LAZ file to MinIO
        logger.info(f"Uploading node {node_id} to {minio_path}")
        upload_local_file(self.client, self.bucket, upload_file, minio_path)

        # Generate and upload metadata
        node_meta = OctreeNode(
            node_id=node_id,
            depth=depth,
            bbox=bbox,
            point_count=count,
            is_leaf=is_leaf,
            children=children_ids,
            parent=parent_id,
            minio_path=minio_path
        )

        meta_tmp = os.path.join(tmp_dir, f"meta_{node_id}.json")
        with open(meta_tmp, "w") as f:
            f.write(node_meta.model_dump_json(indent=2))

        upload_local_file(self.client, self.bucket, meta_tmp, metadata_path, content_type="application/json")

        # Cleanup temp file if it's a child to save disk space during recursion
        if depth > 0:
            try:
                os.remove(input_file)
            except:
                pass
