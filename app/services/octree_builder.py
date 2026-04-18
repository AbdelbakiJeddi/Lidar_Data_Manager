import asyncio
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

from minio import Minio

from app.models import BoundingBox, OctreeNode
from app.core.minio_client import BUCKET_RAW, BUCKET_PROCESSED, upload_local_file, download_file
from app.services.pdal_processor import PDALProcessor, PDALPipelineError
from app.services.las_tools_processor import LasToolsProcessor, LasToolsError

logger = logging.getLogger(__name__)


class OctreeBuilder:
    def __init__(
        self,
        minio_client: Minio,
        dataset_id: str,
        max_depth: int = 8,
        point_threshold: int = 1_000_000,
        temp_dir: str = None
    ):
        self.minio_client = minio_client
        self.dataset_id = dataset_id
        self.max_depth = max_depth
        self.point_threshold = point_threshold
        self.pdal = PDALProcessor()
        self.lastools = LasToolsProcessor()  # Fallback
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix=f"octree_{dataset_id}_")
        self.nodes: List[OctreeNode] = []

    def _should_split(self, depth: int, point_count: int) -> bool:
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

    def build_octree(self, input_file: str, input_in_minio: bool = True, source_bucket: str = BUCKET_RAW) -> List[OctreeNode]:
        logger.info(f"Building octree for dataset {self.dataset_id}")

        local_input = input_file
        if input_in_minio:
            local_input = os.path.join(self.temp_dir, "source.laz")
            download_file(self.minio_client, source_bucket, input_file, local_input)
            logger.info(f"Downloaded source file to {local_input}")

        info = self.pdal.get_info(local_input)
        root_bbox = BoundingBox(**info["bbox"])
        root_point_count = info["point_count"]

        logger.info(f"Root bbox: {root_bbox}, points: {root_point_count}")

        self._process_node(local_input, root_bbox, depth=0, node_id="root", parent_id=None)

        logger.info(f"Octree built. Total nodes: {len(self.nodes)}")
        return self.nodes

    def _process_node(
        self,
        input_file: str,
        bbox: BoundingBox,
        depth: int,
        node_id: str,
        parent_id: Optional[str]
    ) -> OctreeNode:
        try:
            point_count = self.pdal.get_point_count(input_file)
        except (LasToolsError, PDALPipelineError):
            point_count = 0

        logger.debug(f"Processing node {node_id} at depth {depth}, points: {point_count}")

        should_split = self._should_split(depth, point_count)
        children_ids: List[str] = []
        children_nodes: List[OctreeNode] = []

        if should_split:
            octants = bbox.split_into_octants()
            for i, child_bbox in enumerate(octants):
                child_node_id = self._generate_node_id(node_id, i)
                child_output = os.path.join(self.temp_dir, f"node_{child_node_id}.laz")

                try:
                    self.pdal.process_octant(input_file, child_output, child_bbox)

                    if os.path.exists(child_output) and os.path.getsize(child_output) > 0:
                        child_point_count = self.pdal.get_point_count(child_output)

                        if child_point_count > 0:
                            child_node = self._process_node(
                                child_output,
                                child_bbox,
                                depth + 1,
                                child_node_id,
                                node_id
                            )
                            children_nodes.append(child_node)
                            children_ids.append(child_node_id)

                        if os.path.exists(child_output):
                            os.remove(child_output)

                except (LasToolsError, PDALPipelineError) as e:
                    logger.warning(f"Failed to process octant {child_node_id}: {e}")

        is_leaf = not should_split or len(children_ids) == 0

        minio_path = ""
        if is_leaf or point_count > 0:
            final_output = os.path.join(self.temp_dir, f"final_{node_id}.laz")
            shutil.copy(input_file, final_output)
            minio_path = self._upload_node(final_output, depth, node_id)
            if os.path.exists(final_output):
                os.remove(final_output)

        node = OctreeNode(
            node_id=node_id,
            depth=depth,
            bbox=bbox,
            point_count=point_count,
            is_leaf=is_leaf,
            children=children_ids,
            parent=parent_id,
            minio_path=minio_path
        )

        self.nodes.append(node)
        return node

    def cleanup(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temp directory: {self.temp_dir}")

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
            "total_points": sum(n.point_count for n in self.nodes if n.is_leaf)
        }