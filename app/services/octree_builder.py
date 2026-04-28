"""SPSLiDAR Fast Recursive Octree Builder.

Implements the SPSLiDAR sampling algorithm: at each node, a deterministic
sample (every Nth point) stays at the current node while the *remainder*
is partitioned into 8 spatial octants and recursed upon.  Each point in
the dataset appears in exactly **one** octree node (zero duplication).

All heavy point-cloud I/O is handled by PDAL CLI pipelines (C++ engine).
Python only orchestrates the pipeline JSON and manages temp files.
"""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any

from minio import Minio

from app.models import BoundingBox, OctreeNode
from app.core.minio_client import BUCKET_RAW, BUCKET_PROCESSED, upload_local_file, download_file
from app.services.pdal_processor import PDALProcessor, PDALPipelineError

logger = logging.getLogger(__name__)

# Margin applied to child bounding boxes during cropping to prevent
# floating-point exclusion at octant boundaries (SPSLiDAR convention).
BBOX_MARGIN = 0.01


class OctreeBuilder:
    """Build an octree using the SPSLiDAR Fast Recursive algorithm.

    At each recursive level the builder:
    1. Checks the stopping condition (max depth or point threshold).
    2. Samples every Nth point → uploads as the current node's data.
    3. Extracts the remainder (all non-sampled points).
    4. Crops the remainder into 8 spatial octants.
    5. Recurses on each non-empty octant.
    """

    def __init__(
        self,
        minio_client: Minio,
        dataset_id: str,
        max_depth: int = 8,
        point_threshold: int = 1_000_000,
        temp_dir: Optional[str] = None,
    ):
        self.minio_client = minio_client
        self.dataset_id = dataset_id
        self.max_depth = max_depth
        self.point_threshold = point_threshold
        self.pdal = PDALProcessor()
        self.processor = self.pdal
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix=f"octree_{dataset_id}_")
        self.nodes: List[OctreeNode] = []

    # -------------------------------------------------------------- #
    #  Public API
    # -------------------------------------------------------------- #

    def build_octree(
        self,
        input_file: str,
        input_in_minio: bool = True,
        source_bucket: str = BUCKET_RAW,
    ) -> List[OctreeNode]:
        """Build the full octree and return the list of nodes."""

        logger.info(f"Building octree for dataset {self.dataset_id}")

        local_input = input_file
        if input_in_minio:
            local_input = os.path.join(self.temp_dir, "source.laz")
            download_file(self.minio_client, source_bucket, input_file, local_input)
            logger.info(f"Downloaded source file to {local_input}")

        info = self.processor.get_info(local_input)
        bbox_dict = info["bbox"]
        
        # Add a tiny epsilon to the max bounds to ensure points exactly on 
        # the global max boundary are not excluded by the half-open interval < max
        root_bbox = BoundingBox(
            min_x=bbox_dict["min_x"],
            min_y=bbox_dict["min_y"],
            min_z=bbox_dict["min_z"],
            max_x=bbox_dict["max_x"] + 0.001,
            max_y=bbox_dict["max_y"] + 0.001,
            max_z=bbox_dict["max_z"] + 0.001,
        )
        root_point_count = info["point_count"]

        logger.info(f"Root bbox: {root_bbox}, points: {root_point_count}")

        self._process_node(
            local_input, root_bbox, depth=0, node_id="root", parent_id=None
        )

        logger.info(f"Octree built. Total nodes: {len(self.nodes)}")
        return self.nodes

    # -------------------------------------------------------------- #
    #  Recursive processing (SPSLiDAR Fast Recursive)
    # -------------------------------------------------------------- #

    def _process_node(
        self,
        input_file: str,
        bbox: BoundingBox,
        depth: int,
        node_id: str,
        parent_id: Optional[str],
    ) -> OctreeNode:
        """Process a single octree node using SPSLiDAR sampling logic."""

        try:
            point_count = self.processor.get_point_count(input_file)
        except PDALPipelineError:
            point_count = 0

        logger.debug(
            f"Processing node {node_id} at depth {depth}, points: {point_count}"
        )

        # ---- Leaf condition ---- #
        if not self._should_split(depth, point_count):
            # Upload entire file as leaf data
            minio_path = self._upload_node(input_file, depth, node_id)
            node = OctreeNode(
                node_id=node_id,
                depth=depth,
                bbox=bbox,
                point_count=point_count,
                is_leaf=True,
                children=[],
                parent=parent_id,
                minio_path=minio_path,
            )
            self.nodes.append(node)
            return node

        # ---- Recursive step: sample + partition remainder ---- #
        step = max(point_count // self.point_threshold, 2)

        sampled_file = os.path.join(self.temp_dir, f"sampled_{node_id}.laz")
        remainder_file = os.path.join(self.temp_dir, f"remainder_{node_id}.laz")

        # 1. Create the node sample (every Nth point stays here)
        sampled_count = self.processor.sample_nth(input_file, sampled_file, step)
        logger.debug(f"Node {node_id}: sampled {sampled_count} points (step={step})")

        # 2. Create the remainder (all other points → children)
        remainder_count = self.processor.remainder_nth(input_file, remainder_file, step)
        logger.debug(f"Node {node_id}: remainder {remainder_count} points")

        # 3. Upload the sampled file as this node's data
        minio_path = self._upload_node(sampled_file, depth, node_id)
        self._safe_remove(sampled_file)

        # 4. Crop the remainder into 8 octants and recurse
        children_ids: List[str] = []
        octants = bbox.split_into_octants()

        for i, child_bbox in enumerate(octants):
            child_node_id = self._generate_node_id(node_id, i)
            child_file = os.path.join(self.temp_dir, f"octant_{child_node_id}.laz")

            try:
                # Use exact child bbox — PDAL filters.crop uses inclusive
                # bounds so points on the split plane are captured.
                self.processor.crop_to_bbox(remainder_file, child_file, child_bbox)

                if os.path.exists(child_file) and os.path.getsize(child_file) > 0:
                    child_point_count = self.processor.get_point_count(child_file)

                    if child_point_count > 0:
                        child_node = self._process_node(
                            child_file,
                            child_bbox,
                            depth + 1,
                            child_node_id,
                            node_id,
                        )
                        children_ids.append(child_node_id)

                self._safe_remove(child_file)

            except PDALPipelineError as e:
                logger.warning(f"Failed to process octant {child_node_id}: {e}")
                self._safe_remove(child_file)

        # Clean up remainder
        self._safe_remove(remainder_file)

        # Build the current (non-leaf) node
        node = OctreeNode(
            node_id=node_id,
            depth=depth,
            bbox=bbox,
            point_count=sampled_count,
            is_leaf=False,
            children=children_ids,
            parent=parent_id,
            minio_path=minio_path,
        )
        self.nodes.append(node)
        return node

    # -------------------------------------------------------------- #
    #  Helpers
    # -------------------------------------------------------------- #

    def _should_split(self, depth: int, point_count: int) -> bool:
        """Return True if the node should be subdivided further."""
        if depth >= self.max_depth:
            return False
        if point_count <= self.point_threshold:
            return False
        return True

    def _get_minio_path(self, depth: int, node_id: str) -> str:
        return f"datasets/{self.dataset_id}/octree/depth={depth}/node_{node_id}.laz"

    def _generate_node_id(self, parent_id: str, octant_index: int) -> str:
        if parent_id == "root":
            return str(octant_index)
        return f"{parent_id}_{octant_index}"

    def _upload_node(self, local_path: str, depth: int, node_id: str) -> str:
        minio_path = self._get_minio_path(depth, node_id)
        upload_local_file(self.minio_client, BUCKET_PROCESSED, local_path, minio_path)
        return minio_path

    @staticmethod
    def _safe_remove(path: str) -> None:
        """Remove a file if it exists, silently ignoring errors."""
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    def cleanup(self):
        """Remove the temporary working directory."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temp directory: {self.temp_dir}")

    # -------------------------------------------------------------- #
    #  Statistics
    # -------------------------------------------------------------- #

    def get_node_count(self) -> int:
        return len(self.nodes)

    def get_leaf_count(self) -> int:
        return sum(1 for n in self.nodes if n.is_leaf)

    def get_max_depth_reached(self) -> int:
        return max((n.depth for n in self.nodes), default=0)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "total_nodes": self.get_node_count(),
            "leaf_nodes": self.get_leaf_count(),
            "max_depth_reached": self.get_max_depth_reached(),
            "total_points": sum(n.point_count for n in self.nodes if n.is_leaf),
            "sampled_points": sum(
                n.point_count for n in self.nodes if not n.is_leaf
            ),
        }