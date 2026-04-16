import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.core.metadata_models import BoundingBox

logger = logging.getLogger(__name__)


class LasToolsError(Exception):
    pass


class LasToolsProcessor:
    """
    Wrapper for LasTools CLI commands.
    Uses las2las, lasinfo, lasmerge, lasoptimize binaries.
    Native Linux binaries (no Wine needed).
    """
    
    def __init__(self, lastools_path: str = None):
        self.lastools_path = lastools_path or os.environ.get("LASTOOLS_PATH", "/opt/LAStools/bin")
    
    def _run_command(self, tool: str, args: List[str]) -> str:
        """
        Run a LasTools command.
        
        Args:
            tool: Tool name (las2las, lasinfo, etc.)
            args: List of arguments
            
        Returns:
            stdout output
        """
        # Native Linux binary (no .exe extension)
        tool_path = os.path.join(self.lastools_path, tool)
        
        # Fallback to .exe if native not found (for Windows compatibility)
        if not os.path.exists(tool_path):
            tool_path = os.path.join(self.lastools_path, f"{tool}.exe")
        
        cmd = [tool_path] + args
        
        logger.debug(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"LasTools error: {e.stderr}")
            raise LasToolsError(f"{tool} failed: {e.stderr}") from e
    
    def get_info(self, input_file: str) -> Dict[str, Any]:
        """
        Get metadata from LAZ file using lasinfo.
        """
        try:
            output = self._run_command("lasinfo", [
                "-i", input_file,
                "-nc",
                "-nv",
                "-nco",
            ])
            
            point_count = 0
            bbox = {"min_x": 0.0, "min_y": 0.0, "min_z": 0.0, "max_x": 0.0, "max_y": 0.0, "max_z": 0.0}
            
            for line in output.split("\n"):
                line = line.strip()
                if "number of point records" in line.lower():
                    try:
                        point_count = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif "min x y z:" in line.lower():
                    parts = line.split(":")[-1].strip().split()
                    if len(parts) >= 3:
                        bbox["min_x"] = float(parts[0])
                        bbox["min_y"] = float(parts[1])
                        bbox["min_z"] = float(parts[2])
                elif "max x y z:" in line.lower():
                    parts = line.split(":")[-1].strip().split()
                    if len(parts) >= 3:
                        bbox["max_x"] = float(parts[0])
                        bbox["max_y"] = float(parts[1])
                        bbox["max_z"] = float(parts[2])
            
            return {
                "point_count": point_count,
                "bbox": bbox,
                "srs": {},
                "metadata": {"raw": output[:500]}
            }
            
        except Exception as e:
            logger.error(f"Failed to get info for {input_file}: {e}")
            raise LasToolsError(f"Failed to get info: {e}") from e
    
    def get_point_count(self, input_file: str) -> int:
        info = self.get_info(input_file)
        return info["point_count"]
    
    def crop_to_bbox(
        self,
        input_file: str,
        output_file: str,
        bbox: BoundingBox
    ) -> Dict[str, Any]:
        """
        Crop LAZ file to bounding box using las2las.
        """
        try:
            self._run_command("las2las", [
                "-i", input_file,
                "-o", output_file,
                "-keep_xy", str(bbox.min_x), str(bbox.min_y), str(bbox.max_x), str(bbox.max_y),
                "-keep_z", str(bbox.min_z), str(bbox.max_z),
            ])
            
            output_info = self.get_info(output_file)
            
            return {
                "point_count": output_info["point_count"],
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
            
        except Exception as e:
            logger.error(f"Failed to crop file: {e}")
            raise LasToolsError(f"Crop failed: {e}") from e
    
    def optimize(self, input_file: str, output_file: str = None) -> str:
        """
        Optimize LAZ file with spatial indexing using lasoptimize.
        """
        output = output_file or input_file
        
        try:
            self._run_command("lasoptimize", [
                "-i", input_file,
                "-o", output,
            ])
            return output
        except Exception as e:
            logger.warning(f"lasoptimize not available or failed: {e}")
            return input_file
    
    def merge_files(
        self,
        input_files: List[str],
        output_file: str
    ) -> str:
        """
        Merge multiple LAZ files using lasmerge.
        """
        try:
            args = ["-o", output_file]
            for f in input_files:
                args.extend(["-i", f])
            
            self._run_command("lasmerge", args)
            return output_file
            
        except Exception as e:
            logger.error(f"Merge failed: {e}")
            raise LasToolsError(f"Merge failed: {e}") from e
    
    def process_octant(
        self,
        input_file: str,
        output_file: str,
        bbox: BoundingBox,
        optimize: bool = False
    ) -> Dict[str, Any]:
        """
        Process octant: crop to bbox and optionally optimize.
        """
        result = self.crop_to_bbox(input_file, output_file, bbox)
        
        if optimize and result["point_count"] > 0:
            self.optimize(output_file)
        
        return result