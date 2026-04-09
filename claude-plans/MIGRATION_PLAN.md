# LiDAR Migration Plan: GridFS/Local -> MinIO

## 1. Data Preparation
- **Raw Data**: `lasmerge` $\rightarrow$ `lasoptimize` (Octree depth 0-8) $\rightarrow$ Local LAZ blocks.
- **GridFS Data**: Direct stream from MongoDB GridFS $\rightarrow$ MinIO.

## 2. Migration Strategy
- **Tool**: `app/migration_tool.py` (Standalone script using `minio_client.py`).
- **Upload**: Parallel streaming via `ThreadPoolExecutor`.
- **S3 Hierarchy**: `{workspace}/{dataset}/depth_{d}/{node_id}.laz`.
- **Metadata**: Hybrid approach.
    - Keep MongoDB for indexing (update `storage_id` to S3 key).
    - Upload sidecar `.json` files in MinIO for each `.laz` block.

## 3. Execution Phases
1. **Setup**: Init `fastapi-bucket` and verify LAStools.
2. **Manifest**: Map `source` $\rightarrow$ `target_key` with checksums.
3. **Transfer**: Bulk stream LAZ files + JSON sidecars to MinIO.
4. **Verification**: 
    - Checksum audit (Local/GridFS vs S3 ETag).
    - Octree structure audit (Depth 0-8 consistency).
    - API test via `app/main.py` `StreamingResponse`.

## 4. Critical Files
- `app/minio_client.py` (S3 logic)
- `app/migration_tool.py` (New: Migration logic)
- `app/main.py` (API endpoints)
