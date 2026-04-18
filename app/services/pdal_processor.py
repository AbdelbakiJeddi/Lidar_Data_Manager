"""PDAL-based point cloud processor.

Uses native PDAL pipelines instead of LAStools CLI for point cloud operations.
"""

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.metadata_models import BoundingBox
from app.core.settings import PDAL_ENABLED

logger = logging.getLogger(__name__)


class PDALProcessor:
    """
    Processor for LiDAR point cloud data using PDAL.

    Provides native Python PDAL pipeline execution for:
    - Metadata extraction (get_info)
    - Cropping to bounding box (crop_to_bbox)
    - File merging (merge_files)
    - Octant processing (process_octant)
    """

    def __init__(self, use_pdal: bool = None):
        """
        Initialize PDAL processor.

        Args:
            use_pdal: Force PDAL usage. If None, uses PDAL_ENABLED env var.
        """
        self.use_pdal = use_pdal if use_pdal is not None else PDAL_ENABLED
        self._check_pdal_available()

    def _check_pdal_available(self) -> None:
        """Check if PDAL is available on the system."""
        if not self.use_pdal:
            logger.info("PDAL disabled, falling back to LAStools")
            return

        try:
            result = subprocess.run(
                ["pdal", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                logger.warning(f"PDAL binary not functional: {result.stderr}")
                self.use_pdal = False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"PDAL not available: {e}")
            self.use_pdal = False

    def _run_pipeline(self, pipeline: Dict[str, Any]) -> Any:
        """
        Execute a PDAL pipeline.

        Args:
            pipeline: PDAL pipeline JSON structure

        Returns:
            Pipeline output (stdout for reader pipelines, None for writers)
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(pipeline, f)
            pipeline_file = f.name

        try:
            result = subprocess.run(
                ["pdal", "pipeline", pipeline_file],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                raise PDALPipelineError(f"Pipeline failed: {result.stderr}")

            return result.stdout

        except subprocess.TimeoutExpired:
            raise PDALPipelineError("Pipeline execution timed out")
        finally:
            os.unlink(pipeline_file)

    def get_info(self, input_file: str) -> Dict[str, Any]:
        """
        Extract metadata from a LAZ/LAS file using PDAL.

        Args:
            input_file: Path to input LAZ/LAS file

        Returns:
            Dictionary with point_count, bbox, srs, and metadata
        """
        pipeline = {
            "pipeline": [
                input_file,
                {
                    "type": "filters.info"
                }
            ]
        }

        try:
            output = self._run_pipeline(pipeline)
            info = json.loads(output)

            bounds = info.get("bounds", {})
            return {
                "point_count": info.get("count", 0),
                "bbox": {
                    "min_x": bounds.get("X", {}).get("minimum", 0.0),
                    "min_y": bounds.get("Y", {}).get("minimum", 0.0),
                    "min_z": bounds.get("Z", {}).get("minimum", 0.0),
                    "max_x": bounds.get("X", {}).get("maximum", 0.0),
                    "max_y": bounds.get("Y", {}).get("maximum", 0.0),
                    "max_z": bounds.get("Z", {}).get("maximum", 0.0),
                },
                "srs": info.get("srs", {}),
                "metadata": info
            }

        except (json.JSONDecodeError, PDALPipelineError) as e:
            logger.error(f"PDAL get_info failed: {e}")
            raise PDALPipelineError(f"Failed to extract metadata: {e}") from e

    def crop_to_bbox(
        self,
        input_file: str,
        output_file: str,
        bbox: BoundingBox
    ) -> Dict[str, Any]:
        """
        Crop a point cloud to a bounding box using PDAL filters.crop.

        Args:
            input_file: Path to input LAZ/LAS file
            output_file: Path for cropped output file
            bbox: BoundingBox defining crop region

        Returns:
            Dictionary with point_count and output_file path
        """
        pipeline = {
            "pipeline": [
                input_file,
                {
                    "type": "filters.crop",
                    "bounds": (
                        f"([{bbox.min_x}, {bbox.max_x}],"
                        f"[{bbox.min_y}, {bbox.max_y}],"
                        f"[{bbox.min_z}, {bbox.max_z}])"
                    )
                },
                {
                    "type": "writers.las",
                    "filename": output_file,
                    "compression": "true"
                }
            ]
        }

        try:
            self._run_pipeline(pipeline)

            # Get point count of cropped file
            info = self.get_info(output_file)

            return {
                "point_count": info["point_count"],
                "output_file": output_file,
                "bbox": {
                    "min_x": bbox.min_x,
                    "min_y": bbox.min_y,
                    "min_z": bbox.min_z,
                    "max_x": bbox.max_x,
                    "max_y": bbox.max_y,
                    "max_z": bbox.max_z,
                }
            }

        except PDALPipelineError as e:
            logger.error(f"PDAL crop failed: {e}")
            raise

    def merge_files(
        self,
        input_files: List[str],
        output_file: str
    ) -> str:
        """
        Merge multiple LAZ/LAS files using PDAL.

        Args:
            input_files: List of input file paths
            output_file: Path for merged output file

        Returns:
            Path to merged output file
        """
        if not input_files:
            raise ValueError("At least one input file required")

        pipeline = {
            "pipeline": [
                *input_files,
                {
                    "type": "filters.merge"
                },
                {
                    "type": "writers.las",
                    "filename": output_file,
                    "compression": "true"
                }
            ]
        }

        try:
            self._run_pipeline(pipeline)
            return output_file
        except PDALPipelineError as e:
            logger.error(f"PDAL merge failed: {e}")
            raise

    def process_octant(
        self,
        input_file: str,
        output_file: str,
        bbox: BoundingBox,
        optimize: bool = False
    ) -> Dict[str, Any]:
        """
        Process an octant: crop to bounding box and optionally optimize.

        Args:
            input_file: Path to input file
            output_file: Path for output file
            bbox: BoundingBox for cropping
            optimize: If True, apply spatial optimization

        Returns:
            Processing result dictionary
        """
        result = self.crop_to_bbox(input_file, output_file, bbox)

        if optimize and result["point_count"] > 0:
            self._optimize_file(output_file)

        return result

    def _optimize_file(self, input_file: str) -> str:
        """
        Optimize a LAZ file with PDAL for better spatial access.

        Uses PDAL's sort filter for spatial ordering (Hilbert curve).
        """
        temp_file = input_file + ".tmp"

        pipeline = {
            "pipeline": [
                input_file,
                {
                    "type": "filters.sort",
                    "order": "Hilbert"
                },
                {
                    "type": "writers.las",
                    "filename": temp_file,
                    "compression": "true"
                }
            ]
        }

        try:
            self._run_pipeline(pipeline)
            os.replace(temp_file, input_file)
            return input_file
        except PDALPipelineError as e:
            logger.warning(f"PDAL optimization failed: {e}")
            if os.path.exists(temp_file):
                os.unlink(temp_file)
            return input_file


class PDALPipelineError(Exception):
    """Exception raised when PDAL pipeline execution fails."""
    pass
