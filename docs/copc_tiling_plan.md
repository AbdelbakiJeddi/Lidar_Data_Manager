# Implementation Plan: Flat 2D Tiling with COPC Conversion

This plan outlines the migration from the "Fast Recursive Octree" to a "Flat 2D Tiling" workflow. The goal is to provide a robust, data-preserving system where large datasets are split into a simple grid of tiles, each optimized for both download and cloud-native streaming via the COPC format. This version introduces **Celery & Redis** for distributed background processing.

## Infrastructure Updates
*   **Message Broker**: **Redis** (New service in `docker-compose`).
*   **Worker**: A dedicated Celery worker container running the `PDALProcessor` and `TileManager`.
*   **Monitoring (Optional)**: **Flower** for real-time task tracking.

## Proposed Workflow
1.  **Spatial Analysis**: Calculate the global bounding box and determine the optimal grid size (e.g., 500m x 500m or 1000m x 1000m) based on point density.
2.  **Flat Tiling**: Use PDAL's `filters.splitter` to partition the source LAZ into a non-recursive 2D grid.
3.  **COPC Encoding**: Convert each resulting tile into a `.copc.laz` file. This adds an internal spatial index to each tile.
4.  **Cloud Storage**: Upload tiles to MinIO with a flat naming convention: `datasets/{id}/tiles/tile_{x}_{y}.copc.laz`.
5.  **Metadata Indexing**: Store the grid configuration and individual tile metadata in **MongoDB** for fast spatial and administrative lookups.

---

## 1. Architectural Impact & Entity Changes

### Component: MongoDB Models
We are moving from a **Hierarchical (Tree)** model to a **Grid (Flat)** model.

#### [MODIFY] `Dataset` Entity
*   **Remove**: `rootDatablocks` (Octree-specific).
*   **Add**: 
    *   `tiling_strategy`: `"flat_2d_grid"`
    *   `grid_origin`: `[x, y]`
    *   `tile_size_meters`: `500` (for example)
    *   `total_tiles`: `Integer`

#### [REPLACE] `Datablock` / `OctreeNode` with `Tile` Entity
*   **Fields**:
    *   `dataset_id`: `ObjectId`
    *   `grid_index`: `[x, y]` (e.g., `[0, 5]`)
    *   `bbox`: `BoundingBox`
    *   `point_count`: `Long`
    *   `minio_path`: `String` (path to `.copc.laz`)
    *   `file_size_bytes`: `Long`

---

## 2. API & Service Refactoring

### Component: `PDALProcessor`
We need to add a specialized pipeline to handle the split-and-convert operation in one or two steps.

#### [MODIFY] `app/services/pdal_processor.py`
*   Add `create_copc_tile(input_file, output_file, bounds)`: A method to convert a standard LAZ to a COPC file while preserving all precision (scale/offset).
*   Add `split_dataset_to_grid(input_file, output_dir, tile_size)`: Uses `filters.splitter` to generate the initial raw tiles.

### Component: `TileManager` (New Service)
Replace the `OctreeBuilder` with a simpler `TileManager`.

#### [NEW] `app/services/tile_manager.py`
*   **Logic**: 
    1.  Read global metadata.
    2.  Calculate grid dimensions.
    3.  Execute the PDAL splitter.
    4.  Loop through generated files, convert each to COPC, and upload to MinIO.
    5.  Register tiles in the database.

---

## 3. Technical Details: The PDAL Pipeline

### The Splitter Pipeline (Step 1)
```json
[
    "input.laz",
    {
        "type": "filters.splitter",
        "length": 1000,
        "origin_x": 0,
        "origin_y": 0
    },
    {
        "type": "writers.las",
        "filename": "tile_#.laz",
        "forward": "all"
    }
]
```
*   `forward: "all"` is critical: it ensures the output tiles have the exact same Coordinate Reference System (CRS), scale, and offsets as the source.

### The COPC Writer (Step 2)
```json
[
    "tile_1.laz",
    {
        "type": "writers.copc",
        "filename": "tile_1.copc.laz",
        "forward": "all"
    }
]
```
*   This creates the "Cloud Optimized" internal octree within each tile.

---

## 4. Storage Organization (MinIO)
Instead of `depth=1/node_1_2.laz`, we will use a flat, searchable structure:
```text
processed-bucket/
└── datasets/
    └── {dataset_id}/
        ├── metadata.json (Global stats)
        └── tiles/
            ├── tile_0_0.copc.laz
            ├── tile_0_1.copc.laz
            └── tile_1_0.copc.laz
```

---

## 5. Background Task Orchestration (Celery)

To handle large datasets without blocking the API, we will split the work into two levels of tasks:

### Task 1: `orchestrate_tiling(dataset_id)`
*   Downloads the source file.
*   Calculates the grid and runs the **PDAL Splitter**.
*   For every generated tile, it triggers a **Task 2** sub-task.

### Task 2: `process_single_tile(dataset_id, tile_path, coords)`
*   Converts the raw tile to **COPC** format.
*   Uploads the `.copc.laz` to MinIO.
*   Updates the MongoDB `Tile` entity with the final stats.
*   *Note: This allows multiple tiles to be converted in parallel across all CPU cores.*

---

## 6. API Endpoint Changes

### [MODIFY] `POST /api/datasets/process`
*   **New Behavior**: Immediately returns a `task_id` and starts `orchestrate_tiling` in the background.

### [NEW] `GET /api/datasets/{id}/tiles`
*   **Purpose**: Returns a list of all tiles for a dataset.
*   **Query Params**: `min_x, min_y, max_x, max_y` (Spatial filter to return only tiles in an area).

### [DELETE] `GET /api/nodes/{id}`
*   Recursive node fetching is no longer needed.

---

## 7. Verification Plan

### Automated Tests
1.  **Point Count Audit**: Sum the point counts of all tiles and compare them to the original source file. They must match 1:1.
2.  **Precision Check**: Compare the XYZ coordinates of a few random points in the original vs. the new COPC tile to ensure no rounding errors occurred.
3.  **COPC Validation**: Use `copc-lib` or a simple `pdal info` check to verify that the internal `copc` VLR (Variable Length Record) exists.

### Manual Verification
1.  **Download Test**: Download a specific tile and open it in CloudCompare to verify visual integrity.
2.  **Visual Proof**: Drop one of the `.copc.laz` files into [copc.io](https://copc.io) to see if the web-viewer can stream it correctly.

---

## Open Questions for the User
*   **Tile Size**: Do you want a fixed spatial size (e.g., 500m) or a fixed point-count per tile (e.g., 10M points)? Fixed spatial size is usually better for GIS alignment.
*   **Worker Concurrency**: How many parallel workers should we run by default? (Usually equal to the number of CPU cores).
