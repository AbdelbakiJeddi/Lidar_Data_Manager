"""Centralized application settings."""

import os


# LAStools binary path - configurable via environment variable
LASTOOLS_BIN = os.environ.get("LASTOOLS_BIN", "/opt/LAStools/bin")

# PDAL settings
PDAL_ENABLED = os.environ.get("PDAL_ENABLED", "false").lower() == "true"

# MinIO bucket names
BUCKET_RAW = os.environ.get("MINIO_BUCKET_RAW", "lidar-raw")
BUCKET_PROCESSED = os.environ.get("MINIO_BUCKET_PROCESSED", "lidar-processed")

# Octree processing defaults
OCTREE_MAX_DEPTH = int(os.environ.get("OCTREE_MAX_DEPTH", "8"))
OCTREE_POINT_THRESHOLD = int(os.environ.get("OCTREE_POINT_THRESHOLD", "1000000"))
