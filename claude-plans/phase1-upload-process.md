# Phase 1: Data Upload and Initial Processing

## Pipeline Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Upload    │───▶│ Group by    │───▶│   Merge     │───▶│   Create    │
│  (LAZ files)│    │   UTM Zone  │    │  per Zone   │    │  Root Files │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                  │
                                                                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Store in  │◀───│  Optimize   │◀───│   Build     │◀───│  (Phase 2)  │
│  GridFS+Mongo│   │   Files     │    │   Octree    │    │  Subdivide  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## Prerequisites (Before Upload)

Grid cells are created when the **Dataset** is created (not during upload):

```java
// DatasetService.addDataset()
List<GeorefBox> gridCells = GridAllocator.allocateDataset(
    utmZone, datasetBbox, workspace.cellSize
);
```

Each grid cell will get its own octree when data is uploaded.

---

## Step 1: Upload

**Endpoint:**
```
PUT /spslidar/workspaces/{workspace}/datasets/{dataset}/data
Content-Type: multipart/form-data
Body: files=[file1.laz, file2.laz, ...]
```

**Storage:**
```
C:\server\{workspace}_{dataset}\
├── {workspace}_{dataset}_1.laz
├── {workspace}_{dataset}_2.laz
└── ...
```

**Code Path:**
```
DatablockController.addPointCloudToDataset()
    └─► DatablockService.addDataToDataset()
            └─► SystemFileStorageService.storeMultipleFiles()
```

---

## Step 2: Group by UTM Zone

**Purpose:** Files may have different UTM zones. Group and process each zone separately.

```java
// DatablockServiceLasTools.divideDatasetByUTMCells()
Flux.fromIterable(files)
    .flatMap(file -> Mono.zip(
        lasToolsService.getUTMZone(file),  // Extract UTM (e.g., "30N")
        Mono.just(file)
    ))
    .groupBy(Tuple2::getT1)  // Group by UTM zone
```

**UTM Extraction:**
```bash
lasinfo merged.laz -no_check | grep "UTM zone"
# Output: "UTM zone 30N"
```

---

## Step 3: Merge Per UTM Zone

**Purpose:** Combine all files in the same UTM zone into one file.

```java
// For each UTM zone group
lasToolsService.mergeFiles(filesToMerge, targetDirectory)
```

**Command:**
```bash
lasmerge -i file1.laz file2.laz -o {workspace}_{dataset}\{UTMZone}\merged.laz
```

**Output:**
```
C:\server\{workspace}_{dataset}\{UTMZone}\merged.laz
```

**Cleanup:** Original uploaded files are deleted after merge.

---

## Step 4: Create Root Files

**Purpose:** For each grid cell, extract points within its bounds as the octree root (node 0).

```java
// DatablockServiceLasTools.createRootFileOfGrid()
lasToolsService.createRootFile(inputDirectory, outputDirectory, dataset, grid)
```

**Command:**
```bash
las2las -i merged.laz -o root.laz -keep_xy \
    <southwest_easting> <southwest_northing> \
    <northeast_easting> <northeast_northing>
```

**Output Structure:**
```
C:\server\{workspace}_{dataset}\{UTMZone}\{georefIdentifier}\
└── {workspace}_{dataset}_0_root.laz
```

**Note:** If a grid cell has no points, no file is created (false positive grid).

---

## Step 5: Build Octree (Phase 2)

**Purpose:** Recursively subdivide each root into 8 children until max depth or point threshold.

```java
// DatablockServiceLasTools.octreeBuilding()
lasToolsAlgorithmInterface.octreeBuildingAlgorithm(rootDatablock, dataBlockSize)
```

**Operations per node:**
1. `createChildNode()` - Crop points to child bounds (`las2las -keep_xyz`)
2. `sampleDataFromFile()` - Downsample if too many points (`las2las -keep_random_fraction`)
3. Recurse until `depth >= maxDepth` (default: 8)

---

## Step 6: Optimize Files

**Purpose:** Improve LAZ file compression and access patterns.

```java
// DatablockServiceLasTools.storeOctree()
lasToolsService.optimizeFile(datablock)
```

**Command:**
```bash
lasoptimize -i input.laz -o optimized.laz
```

---

## Step 7: Store in GridFS + MongoDB

**File Storage (GridFS):**
```java
// GridFileStorageService.addFile()
fileRepositoryInterface.addFile(datablock, dataset)
```

- LAZ file stored in MongoDB GridFS
- Returns `ObjectId` for the file

**Metadata Storage (MongoDB):**
```java
// DatablockRepositoryMongo.save()
datablockRepositoryInterface.save(datablock, workspace, dataset)
```

**Collection:** `{workspace}_datablocks`

**Document:**
```javascript
{
  "_id": ObjectId("..."),
  "datasetName": "my-dataset",
  "node": 42,
  "cell": { /* GeorefBox */ },
  "depth": 3,
  "numberOfPoints": 50000,
  "children": [337, 338, 339, 340, 341, 342, 343, 344],
  "fileId": ObjectId("...")  // Reference to GridFS file
}
```

---

---

## GridFS Storage Explained

**GridFS** is MongoDB's specification for storing large files that exceed the BSON document limit (16MB).

### How GridFS Works

1. **Chunks the file** into smaller pieces (configurable, default 255KB)
2. **Stores chunks** in `fs.chunks` collection
3. **Stores metadata** in `fs.files` collection

### SPSLiDAR Configuration

```properties
persistence.chunkSize=2097152  # 2MB chunks
```

### Storage Structure

```
MongoDB: spslidar
├── fs.files (metadata)
│   └── {
│         "_id": ObjectId("..."),
│         "filename": "ws1_ds1_42_optimized.laz",
│         "length": 15728640,
│         "chunkSize": 2097152
│       }
│
└── fs.chunks (binary data)
    ├── { "files_id": ObjectId("..."), "n": 0, "data": <binary> }
    ├── { "files_id": ObjectId("..."), "n": 1, "data": <binary> }
    └── ...
```

### Why GridFS?

| Pros | Cons |
|------|------|
| Single database for metadata + files | MongoDB storage expensive at scale |
| Automatic chunking & streaming | Not ideal for files < 16MB |
| Reactive API support | Slower than object storage (MinIO/S3) |

> **Note:** The MinIO migration plan aims to replace GridFS with S3-compatible object storage for better cost efficiency and performance.

---

## Cleanup

**On Success or Error:**
```java
// DatablockServiceLasTools.addDataToDataset()
.doOnError(throwable -> systemFileStorageService.cleanDirectory(workspace, dataset))
.doOnNext(datablock -> systemFileStorageService.cleanDirectory(workspace, dataset))
```

All temporary files in `C:\server\{workspace}_{dataset}\` are deleted.

---

## Configuration

```properties
# application.properties
file.upload-dir=C:\server
file.merge-dir=C:\server\merge
persistence.chunkSize=2097152      # GridFS chunk size (2MB)
octree.maxDepth=8                   # Maximum octree depth
lastools.algorithm=fastRecursiveOctreeBuilding
```

---

## Key Classes

| Class | Responsibility |
|-------|----------------|
| `DatablockController` | HTTP endpoint for upload |
| `DatablockServiceLasTools` | Orchestrates entire pipeline |
| `SystemFileStorageService` | File system operations |
| `LasToolsService` | Wraps LASTools CLI commands |
| `GridFileStorageService` | GridFS file storage |
| `DatablockRepositoryMongo` | MongoDB datablock metadata |

---

## Error Handling

| Error | When | Response |
|-------|------|----------|
| `DatasetHasDataAssociated` | Dataset already has data | 409 Conflict |
| `ElementNotFound` | Workspace/dataset doesn't exist | 404 Not Found |
| `NoUTMZoneInFile` | File missing UTM zone | 415 Unsupported Media Type |

---

*Document created for architecture planning purposes.*
