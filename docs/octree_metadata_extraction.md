# Octree Building and Metadata Extraction in SPSLiDAR

This document outlines the architecture, algorithms, and metadata structures used in the SPSLiDAR project for parsing, processing, and indexing point cloud data (LAZ files). It is intended to serve as a comprehensive guide for migrating or implementing the same logic in another application (e.g., a Python/FastAPI based app).

## 1. Octree Building Algorithms

The project utilizes `LAStools` via CLI commands wrapped in Java `ProcessBuilder` (specifically `las2las`, `lasduplicate`, etc.) to recursively partition point cloud datasets into an octree structure. There are two primary algorithms implemented: **Fast Recursive** and **Slow Recursive**.

### A. Fast Recursive Octree Building
**Implementation Class:** `FastRecursiveOctreeBuilding.java`

**Core Logic:**
This approach uses a deterministic sampling method (every Nth point) to partition the data efficiently at each depth level.

1. **Base Condition:**
   - The recursion stops if the current node's depth reaches the maximum configured depth (`octreeProperties.getMaxDepth()`).
   - The remaining points in the node are converted into a "database-ready" file (`convertMaxDepthFileToBDReady`) without further division.

2. **Sampling & Partitioning (Recursive Step):**
   - **Determine Step (`N`):** The algorithm calculates `N = total_points / max_datablock_size`.
   - **Keep/Drop Split:** Using `las2las`, it simultaneously creates two files:
     - The **sampled node file**: Keeps every Nth point (`-keep_every_nth N`). This file stays at the current octree node.
     - The **remaining points file**: Drops every Nth point (`-drop_every_nth N`). This file contains the points to be passed down to the children.

3. **Spatial Division:**
   - The bounding box of the current node is divided into 8 equal sub-regions (octants).
   - For each child octant, `las2las -keep_xyz <min_x> <min_y> <min_z> <max_x> <max_y> <max_z>` is executed on the **remaining points file** to extract only the points falling within that specific octant.
   - A margin (`nodeMargin = 0.01`) is applied to bounding boxes to prevent floating-point exclusion errors.
   - If a child node file is created and exists (points were found), the algorithm recursively calls itself on the child node.
   - Temporary files are deleted upon completion.

### B. Slow Recursive Octree Building
**Implementation Class:** `SlowRecursiveOctreeBuilding.java`

**Core Logic:**
This approach uses a random fraction sampling method and relies on point deduplication to separate the sampled node points from the remaining points. It is generally slower due to the merging/deduplication step.

1. **Base Condition:**
   - The recursion stops if the current node's total point count is less than the `maxDataBlockSize`. If true, it returns the node as is.

2. **Sampling & Deduplication (Recursive Step):**
   - **Tag Parent:** Changes the user data of all points in the current file to `0` (`las2las -set_user_data 0`).
   - **Sample:** Samples a random fraction of the points (`-keep_random_fraction`) calculated as `maxDataBlockSize / total_points`.
   - **Tag Sample:** Changes the user data of the sampled points to `1` (`las2las -set_user_data 1`).
   - **Merge & Deduplicate:** Merges the parent file (user data 0) with the sampled file (user data 1) using `lasduplicate -merged -unique_xyz`. Because the sampled points share exact XYZ coordinates with points in the parent file, the duplicate is removed, effectively subtracting the sampled points from the main pool.
   - **Extract Remaining:** Extracts the remaining points by keeping only points with user data `0` (`las2las -keep_user_data 0`).

3. **Spatial Division:**
   - Similar to the Fast method, the remaining points are spatially filtered into 8 octants using `-keep_xyz`.
   - Recursion continues for each populated child node.

---

## 2. Metadata Extraction and Storage

Metadata is managed at two main levels: the **Dataset** (global collection) and the **Datablock** (individual octree node).

### A. Dataset-Level Metadata
**Entity:** `Dataset.java`

This structure represents the entirely georeferenced point cloud dataset.

*   `datasetName` (String): Name of the dataset.
*   `workspaceName` (String): Associated workspace.
*   `description` (String): User-provided description.
*   `date` (LocalDateTime): Acquisition date.
*   `bbox` (GeorefBox): The global bounding box encapsulating the entire dataset.
*   `dataBlockSize` (Integer): The target number of points per datablock node.
*   `dataBlockFormat` (String): Format of the blocks (e.g., LAZ).
*   `rootDatablocks` (Map<String, List<GeorefBox>>): A map linking UTM zones to their corresponding root octree grids (bounding boxes).
*   `files` (List<String>): List of original files uploaded for this dataset.

### B. Datablock-Level Metadata (Octree Node)
**Entity:** `Datablock.java` & `AbstractDatablock.java`

This structure represents a single node within the octree.

*   `id` (Integer): Hierarchical ID. Calculated as `parentIndex * 8 + localIndex + 1`.
*   `depth` (Integer): The depth level of this node in the octree (0 = root).
*   `georefBox` (GeorefBox): The specific bounding box coordinates for this node (SouthWestBottom, NorthEastTop).
*   `numberOfPoints` (Long): The exact number of points sampled and stored in this specific node.
*   `UTMZone` (String): The UTM zone (e.g., "30N") this block belongs to.
*   `UTMZoneLocalGrid` (GeorefBox): The local grid reference.
*   `lazFileAssociated` (String): The path or identifier of the actual `.laz` file storing this node's sampled points.
*   `tmpOpsFile` (String): Temporary file path used during the LasTools processing pipeline.
*   `children` (List<Integer>): A list of integer IDs pointing to the child datablocks of this node.

### C. Extraction Mechanisms
**Service:** `LasToolsService.java`

1.  **Point Counting:** 
    - Uses a `LazReaderInterface` (often calling an external Python process via `pylas`) to retrieve the total number of points in a file (`getNumberOfPoints`).
2.  **UTM Zone Extraction:**
    - Executes `lasinfo -no_check <file>`.
    - Captures the standard error/output streams.
    - Searches for the string `"UTM"`.
    - Uses a Regular Expression `\d{2}[A-Z]{1}` (e.g., `30N`, `31T`) to extract the exact UTM zone. If missing, it throws a `NoUTMZoneInFile` exception.
3.  **File Naming Convention:**
    - Temporary and final files are generated dynamically during processing. Names follow the pattern: `<base_name>_<original_id>_<node_id>_<extension_tag>.laz`. Extension tags include `udmod` (user data modified), `bd` (database ready), `merged`, `pready` (partition ready), and `base`.
