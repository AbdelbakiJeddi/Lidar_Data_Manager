# Architecture Revision - LiDAR Data Manager

Date: 2026-04-18

## Goals

- Separate configuration from implementation details.
- Improve lifecycle handling for infrastructure dependencies.
- Make point-cloud processing backend selection (PDAL vs LAStools) explicit and resilient.
- Preserve existing API contracts while improving internal reliability.

## Revised Architecture

## 1) Configuration Layer

- Centralized typed settings in `app/core/settings.py` using `pydantic-settings`.
- Added a cached settings factory (`get_settings`) for consistent access.
- Kept backward-compatible constants to avoid breaking existing imports.

## 2) Infrastructure Layer

- `app/core/minio_client.py` now reads endpoint/credentials/buckets from centralized settings.
- `app/core/mongo_client.py` now reads URI/database from centralized settings and adds `close_mongo_client()`.

## 3) Application Lifecycle

- `app/main.py` now uses FastAPI lifespan instead of startup/shutdown decorators.
- Startup ensures MinIO buckets and MongoDB indexes.
- Shutdown closes the async Mongo client for cleaner resource management.

## 4) Processing Layer

- `app/services/pdal_processor.py` now uses `pdal info --metadata --summary` for robust metadata extraction.
- Added `get_point_count()` to PDAL processor.
- `app/services/octree_builder.py` now picks an active processor (`PDALProcessor` if available, otherwise `LasToolsProcessor`) and uses that consistently.

## Functional Impact

- Metadata endpoint becomes more reliable when PDAL is enabled.
- Octree generation no longer depends on a missing PDAL method.
- Fallback behavior to LAStools is now explicit and consistent.

## Compatibility

- Existing routes are unchanged:
  - `POST /lidar/upload`
  - `POST /lidar/process/{dataset_id}`
  - `GET /lidar/datasets`
  - `GET /lidar/datasets/{dataset_id}`
  - `GET /lidar/datasets/{dataset_id}/nodes`
  - `GET /lidar/datasets/{dataset_id}/info`
  - `GET /lidar/nodes/{dataset_id}/{node_id}`
  - `GET /lidar/nodes/{dataset_id}/{node_id}/download`
  - `GET /health`

## Next Iteration (Recommended)

- Introduce a dedicated service layer for dataset orchestration (`DatasetService`) to move business logic out of API routers.
- Add API key or JWT authentication and request-level rate limiting for heavy operations.
- Add retries/timeouts around MinIO upload/download and node persistence writes.
- Add test coverage for:
  - settings loading
  - lifespan startup/shutdown
  - processor fallback behavior
  - octree processing happy/failure paths
