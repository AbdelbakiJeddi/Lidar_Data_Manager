"""PDAL-based point cloud processor.

Uses native PDAL pipelines for point cloud operations.
"""

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.metadata_models import BoundingBox
from app.core.settings import get_settings

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

    def __init__(self, require_available: bool = True):
        """
        Initialize PDAL processor.

        Args:
            require_available: If True, raise when PDAL is unavailable.
        """
        settings = get_settings()
        self.pdal_bin = settings.pdal_bin
        self.pdal_version = self._check_pdal_available(require_available=require_available)

    def _check_pdal_available(self, require_available: bool = True) -> Optional[str]:
        """Check if PDAL is available on the system and return version."""

        try:
            result = subprocess.run(
                [self.pdal_bin, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                msg = f"PDAL binary not functional: {result.stderr.strip()}"
                if require_available:
                    raise PDALPipelineError(msg)
                logger.warning(msg)
                return None
            return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            msg = f"PDAL not available: {e}"
            if require_available:
                raise PDALPipelineError(msg) from e
            logger.warning(msg)
            return None

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
                [self.pdal_bin, "pipeline", pipeline_file],
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
        try:
            result = subprocess.run(
                [self.pdal_bin, "info", "--metadata", "--summary", input_file],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise PDALPipelineError(f"pdal info failed: {result.stderr.strip()}")

            info = json.loads(result.stdout)
            metadata = info.get("metadata", {})
            summary = info.get("summary", {})
            bounds = summary.get("bounds", {})

            count = self._extract_point_count(metadata, summary)
            bbox = self._extract_bbox(bounds)

            return {
                "point_count": int(count),
                "bbox": bbox,
                "srs": summary.get("srs", {}),
                "metadata": info,
            }
        except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as e:
            logger.error(f"PDAL get_info failed: {e}")
            raise PDALPipelineError(f"Failed to extract metadata: {e}") from e

    def _extract_point_count(self, metadata: Dict[str, Any], summary: Dict[str, Any]) -> int:
        """Extract point count from multiple PDAL info output variants."""
        candidates = [
            metadata.get("count"),
            summary.get("num_points"),
            metadata.get("readers.las", {}).get("count"),
        ]
        for value in candidates:
            if value is not None:
                return int(value)
        return 0

    def _extract_bbox(self, bounds: Dict[str, Any]) -> Dict[str, float]:
        """Extract bbox from multiple PDAL summary bounds formats."""
        if {"minx", "miny", "minz", "maxx", "maxy", "maxz"}.issubset(bounds.keys()):
            return {
                "min_x": float(bounds["minx"]),
                "min_y": float(bounds["miny"]),
                "min_z": float(bounds["minz"]),
                "max_x": float(bounds["maxx"]),
                "max_y": float(bounds["maxy"]),
                "max_z": float(bounds["maxz"]),
            }

        x = bounds.get("X", {})
        y = bounds.get("Y", {})
        z = bounds.get("Z", {})
        return {
            "min_x": float(x.get("minimum", 0.0)),
            "min_y": float(y.get("minimum", 0.0)),
            "min_z": float(z.get("minimum", 0.0)),
            "max_x": float(x.get("maximum", 0.0)),
            "max_y": float(y.get("maximum", 0.0)),
            "max_z": float(z.get("maximum", 0.0)),
        }

    def get_point_count(self, input_file: str) -> int:
        """Return the number of points from a point cloud file."""
        return int(self.get_info(input_file).get("point_count", 0))

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
