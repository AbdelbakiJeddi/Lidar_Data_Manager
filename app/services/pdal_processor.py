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

BBOX_MARGIN = 0.01


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
                timeout=3600
            )

            if result.returncode != 0:
                raise PDALPipelineError(f"Pipeline failed: {result.stderr}")

            return result.stdout

        except subprocess.TimeoutExpired:
            raise PDALPipelineError("Pipeline execution timed out")
        finally:
            os.unlink(pipeline_file)

    def get_info(self, input_file: str, override_srs: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract metadata from a LAZ/LAS file using PDAL.

        Args:
            input_file: Path to input LAZ/LAS file
            override_srs: Optional SRS to force (e.g. 'EPSG:32631')

        Returns:
            Dictionary with point_count, bbox, geographic_bbox, srs_wkt, and metadata
        """
        try:
            cmd = [self.pdal_bin, "info", "--summary", input_file]
            if override_srs:
                cmd.extend(["--readers.las.override_srs", override_srs])

            result = subprocess.run(
                cmd,
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
            srs_info = summary.get("srs", {})
            
            if not srs_info.get("wkt"):
                srs_info = metadata.get("readers.las", {}).get("srs", {})
            
            srs_wkt = override_srs or srs_info.get("wkt") or srs_info.get("compoundwkt")

            count = self._extract_point_count(metadata, summary)
            bbox = self._extract_bbox(bounds)
            
            # Compute geographic bbox by reprojecting native bbox using pyproj
            geographic_bbox = None
            if bbox is not None and srs_wkt:
                geographic_bbox = self._reproject_bbox_to_wgs84(bbox, srs_wkt)

            return {
                "point_count": int(count),
                "bbox": bbox,
                "geographic_bbox": geographic_bbox,
                "srs_wkt": srs_wkt,
                "srs": srs_info,
                "metadata": info,
            }
        except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as e:
            logger.error(f"PDAL get_info failed: {e}")
            raise PDALPipelineError(f"Failed to extract metadata: {e}") from e

    def _reproject_bbox_to_wgs84(self, bbox: Dict[str, float], srs_wkt: str) -> Optional[Dict[str, float]]:
        """Reproject a native bounding box to WGS84 (EPSG:4326) using pyproj."""
        try:
            from pyproj import Transformer, CRS
            
            source_crs = CRS.from_user_input(srs_wkt)
            
            # If it's already geographic, just return as-is
            if source_crs.is_geographic:
                logger.info("Dataset is already in geographic coordinates, no reprojection needed")
                return bbox
            
            transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
            
            # Transform all four corners for accuracy
            corners_x = [bbox["min_x"], bbox["min_x"], bbox["max_x"], bbox["max_x"]]
            corners_y = [bbox["min_y"], bbox["max_y"], bbox["min_y"], bbox["max_y"]]
            
            lons, lats = transformer.transform(corners_x, corners_y)
            
            geo_bbox = {
                "min_x": min(lons),
                "min_y": min(lats),
                "max_x": max(lons),
                "max_y": max(lats),
                "min_z": bbox.get("min_z", -1000.0),
                "max_z": bbox.get("max_z", 1000.0),
            }
            
            logger.info(f"Reprojected native bbox to WGS84: {geo_bbox}")
            return geo_bbox
            
        except Exception as e:
            logger.warning(f"Failed to reproject bbox to WGS84: {e}")
            return None

    def _extract_geographic_bbox(self, boundary: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """Extract geographic bbox from PDAL info boundary (GeoJSON)."""
        if not boundary or boundary.get("type") != "Polygon":
            return None
        
        coords = boundary.get("coordinates", [[]])[0]
        if not coords:
            return None
        
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        
        return {
            "min_x": min(lons),
            "min_y": min(lats),
            "max_x": max(lons),
            "max_y": max(lats),
            "min_z": -1000.0, # Boundary is 2D
            "max_z": 1000.0,
        }

    def _reproject_boundary_to_wgs84(self, boundary: Dict[str, Any], srs_wkt: str) -> Optional[Dict[str, Any]]:
        """Reproject a GeoJSON Polygon or MultiPolygon boundary to WGS84."""
        geom_type = boundary.get("type")
        if geom_type not in ["Polygon", "MultiPolygon"]:
            return None
            
        try:
            from pyproj import Transformer, CRS
            source_crs = CRS.from_user_input(srs_wkt)
            
            if source_crs.is_geographic:
                return boundary
                
            transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
            
            def transform_ring(ring):
                lons, lats = transformer.transform([c[0] for c in ring], [c[1] for c in ring])
                return [[lon, lat] for lon, lat in zip(lons, lats)]
                
            coords = boundary.get("coordinates", [])
            new_coords = []
            
            if geom_type == "Polygon":
                for ring in coords:
                    new_coords.append(transform_ring(ring))
            elif geom_type == "MultiPolygon":
                for poly in coords:
                    new_poly = []
                    for ring in poly:
                        new_poly.append(transform_ring(ring))
                    new_coords.append(new_poly)
            
            return {
                "type": geom_type,
                "coordinates": new_coords
            }
        except Exception as e:
            logger.warning(f"Failed to reproject boundary: {e}")
            return None

    def get_boundary(self, input_file: str, srs_wkt: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Compute the true hexagonal boundary of the point cloud and reproject to WGS84."""
        try:
            cmd = [self.pdal_bin, "info", "--boundary", input_file]
            if srs_wkt:
                cmd.extend(["--readers.las.override_srs", srs_wkt])
                
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                logger.warning(f"pdal info --boundary failed: {result.stderr.strip()}")
                return None
                
            info = json.loads(result.stdout)
            boundary_obj = info.get("boundary", {})
            boundary_json = boundary_obj.get("boundary_json")
            
            if boundary_json and srs_wkt:
                return self._reproject_boundary_to_wgs84(boundary_json, srs_wkt)
                
            return boundary_json
        except Exception as e:
            logger.warning(f"Failed to extract exact boundary: {e}")
            return None

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
                    "type": "filters.expression",
                    "expression": (
                        f"X >= {bbox.min_x} && X < {bbox.max_x} && "
                        f"Y >= {bbox.min_y} && Y < {bbox.max_y} && "
                        f"Z >= {bbox.min_z} && Z < {bbox.max_z}"
                    )
                },
                {
                    "type": "writers.las",
                    "filename": output_file,
                    "compression": "true",
                    "forward": "all"
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

    def crop_to_polygon(
        self,
        input_file: str,
        output_file: str,
        wkt_polygon: str,
        min_z: float = -1e10,
        max_z: float = 1e10,
        target_srs: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Crop a point cloud to an arbitrary polygon using PDAL filters.crop.

        Args:
            input_file: Path to input LAZ/LAS file
            output_file: Path for cropped output file
            wkt_polygon: WKT POLYGON string defining the crop region
            min_z: Minimum Z filter
            max_z: Maximum Z filter
            target_srs: Optional SRS to reproject points to (e.g. 'EPSG:4326')
        """
        stages = [
            input_file,
            {
                "type": "filters.crop",
                "polygon": wkt_polygon
            },
            {
                "type": "filters.expression",
                "expression": f"Z >= {min_z} && Z < {max_z}"
            }
        ]

        if target_srs:
            stages.append({
                "type": "filters.reprojection",
                "out_srs": target_srs
            })

        stages.append({
            "type": "writers.las",
            "filename": output_file,
            "compression": "true",
            "forward": "all"
        })

        pipeline = {"pipeline": stages}

        try:
            self._run_pipeline(pipeline)
            info = self.get_info(output_file)
            return {
                "point_count": info["point_count"],
                "output_file": output_file,
            }
        except PDALPipelineError as e:
            logger.error(f"PDAL polygon crop failed: {e}")
            raise

    def crop_to_octants(
        self,
        input_file: str,
        output_dir: str,
        octants: List[BoundingBox],
        prefix: str = "octant",
    ) -> Dict[int, str]:
        """Crop input to all 8 octants using a single branched PDAL pipeline.

        This reads the file EXACTLY ONCE and splits it into 8 outputs simultaneously.

        Args:
            input_file: Path to input LAZ/LAS file
            output_dir: Directory for output files
            octants: List of 8 BoundingBoxes (the octant regions)
            prefix: Prefix for output filenames

        Returns:
            Dictionary mapping octant_index -> output_file path
        """
        output_files: Dict[int, str] = {}
        
        stages = [
            {
                "filename": input_file,
                "tag": "reader"
            }
        ]

        for i, oct in enumerate(octants):
            output_path = os.path.join(output_dir, f"{prefix}_{i}.laz")
            output_files[i] = output_path
            
            bbox = oct.with_margin(BBOX_MARGIN)
            crop_tag = f"crop_{i}"
            
            stages.append({
                "type": "filters.crop",
                "bounds": f"([{bbox.min_x}, {bbox.max_x}], [{bbox.min_y}, {bbox.max_y}], [{bbox.min_z}, {bbox.max_z}])",
                "inputs": ["reader"],
                "tag": crop_tag
            })
            
            stages.append({
                "type": "writers.las",
                "filename": output_path,
                "compression": "true",
                "forward": "all",
                "inputs": [crop_tag]
            })

        pipeline = {"pipeline": stages}

        try:
            self._run_pipeline(pipeline)
            return output_files
        except PDALPipelineError as e:
            logger.error(f"PDAL crop_to_octants failed: {e}")
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
                    "compression": "true",
                    "forward": "all"
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

    # ------------------------------------------------------------------ #
    #  SPSLiDAR sampling methods (pure PDAL CLI pipelines)
    # ------------------------------------------------------------------ #

    def sample_nth(
        self,
        input_file: str,
        output_file: str,
        step: int,
    ) -> int:
        """Keep every *step*-th point (the node sample).

        Uses native PDAL ``filters.decimation`` — all I/O runs in C++.

        Args:
            input_file:  Path to input LAZ/LAS file.
            output_file: Path for sampled output file.
            step:        Decimation step (keep every Nth point).

        Returns:
            Number of points written to *output_file*.
        """
        pipeline = {
            "pipeline": [
                input_file,
                {"type": "filters.decimation", "step": step},
                {
                    "type": "writers.las",
                    "filename": output_file,
                    "compression": "true",
                },
            ]
        }

        try:
            self._run_pipeline(pipeline)
            return self.get_point_count(output_file)
        except PDALPipelineError as e:
            logger.error(f"PDAL sample_nth failed: {e}")
            raise

    def remainder_nth(
        self,
        input_file: str,
        output_file: str,
        step: int,
    ) -> int:
        """Drop every *step*-th point, keeping the remainder for children.

        Builds a multi-reader pipeline that reads *input_file* ``step - 1``
        times, each with a different ``offset`` (1 … step-1), then merges
        the streams.  All I/O runs in PDAL's C++ engine.

        Args:
            input_file:  Path to input LAZ/LAS file.
            output_file: Path for remainder output file.
            step:        Decimation step (same value used in ``sample_nth``).

        Returns:
            Number of points written to *output_file*.
        """
        stages: list = []
        tags: list = []

        for i in range(1, step):
            reader_tag = f"r{i}"
            dec_tag = f"d{i}"
            stages.append({
                "type": "readers.las",
                "filename": input_file,
                "tag": reader_tag,
            })
            stages.append({
                "type": "filters.decimation",
                "step": step,
                "offset": i,
                "inputs": [reader_tag],
                "tag": dec_tag,
            })
            tags.append(dec_tag)

        stages.append({"type": "filters.merge", "inputs": tags})
        stages.append({
            "type": "writers.las",
            "filename": output_file,
            "compression": "true",
        })

        pipeline = {"pipeline": stages}

        try:
            self._run_pipeline(pipeline)
            return self.get_point_count(output_file)
        except PDALPipelineError as e:
            logger.error(f"PDAL remainder_nth failed: {e}")
            raise


class PDALPipelineError(Exception):
    """Exception raised when PDAL pipeline execution fails."""
    pass
