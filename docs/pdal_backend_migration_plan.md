# PDAL Backend Migration Plan

This plan details the migration from LAStools CLI dependency to native Python PDAL bindings (`python-pdal`).

## Overview
- Replacing LAStools with PDAL requires the [`pdal`](https://pdal.io/) system binary and `python-pdal` package to be installed on the host/Docker container.
- We will shift the Octree generation toward PDAL's native capabilities or configure it to output COPC (Cloud Optimized Point Cloud) structure for efficient partitioning.

## Proposed Changes

---

### Phase 1: PDAL Backend Integration (Replacing LasTools)

Currently, the application relies on `las_tools_processor.py` which executes shell commands for `lasinfo`, `las2las`, and `lasmerge`. This will be replaced with robust PDAL pipelines.

#### [NEW] `app/services/pdal_processor.py`
Finalize the `PDALProcessor` class to manage point cloud operations natively in Python.
- Create pipeline for `get_info()` (Equivalent to `lasinfo`).
- Create pipeline for `crop_to_bbox()` using PDAL's `filters.crop` (Equivalent to `las2las -keep_xy`).
- Create pipeline for `merge_files()` using PDAL's `filters.merge` (Equivalent to `lasmerge`).

#### [MODIFY] `app/services/octree_builder.py`
- Update the octree partitioning logic to invoke `PDALProcessor.process_octant()` instead of the legacy `LasToolsProcessor`.
- Ensure async execution of PDAL pipelines using FastAPI's background tasks or an async executor to prevent blocking the main thread during heavy processing.

#### [MODIFY] Requirements & Dockerfile
- Add `pdal` to system dependencies in `Dockerfile` (e.g., `apt-get install pdal libpdal-dev`).
- Add `pdal` to `requirements.txt`.

## Verification Plan
- Run integration tests simulating a file upload.
- Verify that `pdal_processor.py` successfully reads bounds and point counts.
- Check MinIO buckets to ensure valid `.laz`/`.copc.laz` objects are saved successfully without the use of LAStools scripts.
