# MongoDB Optimization Plan for MinIO File Metadata

## Overview
This document outlines the strategy to optimize MinIO file metadata storage in MongoDB for faster retrieval and better data organization.

---

## Current State

### Database Structure
- **Collection**: `datasets`
- **Records**: One document per uploaded file
- **Fields**: `id`, `dataset_name`, `filename`, `object_name`, `size`, `status`, `created_at`, `updated_at`, `point_count`, `node_count`, `bbox`, `error`

### Existing Query Methods
- By `dataset_name` - retrieve all files in a group
- By `id` - retrieve single file by ID
- By `object_name` - retrieve file by MinIO path

### Problems
1. No database indexes → all queries do full collection scans
2. ID mismatch: MinIO uses one ID, MongoDB stores another
3. No deduplication detection
4. No audit trail (who uploaded what)
5. Limited filtering capabilities
6. No file hash for change detection

---

## Proposed Improvements

### 1. MongoDB Indexes (Query Performance)

#### Index on `dataset_name`
**Purpose**: Fast retrieval of all files in a dataset group
```
db.datasets.createIndex({ "dataset_name": 1 })
```
**Benefit**: Instead of scanning all 10,000 documents, MongoDB jumps to 50 files in "iowa_survey" group.
**Query impact**: `get_by_dataset_name()` goes from O(n) to O(log n)

#### Index on `object_name`
**Purpose**: Fast lookup by exact MinIO path
```
db.datasets.createIndex({ "object_name": 1 }, { "unique": true })
```
**Benefit**: Prevents duplicate uploads with same path; enables instant file lookup.
**Query impact**: `get_by_object_name()` becomes instant

#### Compound Index on `(dataset_name, filename)`
**Purpose**: Fast lookup of specific file in group
```
db.datasets.createIndex({ "dataset_name": 1, "filename": 1 })
```
**Benefit**: Find "iowa.laz" in "iowa_survey" without scanning the group.
**Use case**: Before processing, check if file already exists instantly.

#### Index on `status`
**Purpose**: Fast filtering by processing state
```
db.datasets.createIndex({ "status": 1 })
```
**Benefit**: Instantly find all failed/processing/completed uploads.
**Use case**: Dashboard showing "5 files failed" loads instantly.

#### Compound Index on `(dataset_name, status, created_at)`
**Purpose**: Fast time-range queries within a dataset
```
db.datasets.createIndex({ "dataset_name": 1, "status": 1, "created_at": -1 })
```
**Benefit**: "Find all uploaded files in iowa_survey from last 7 days" is fast.

---

### 2. Richer File Metadata

#### New Fields to Add

| Field | Type | Purpose |
|-------|------|---------|
| `file_hash` | string (SHA256) | Detect duplicate uploads |
| `file_extension` | string | Filter by .laz vs .las |
| `file_size_mb` | float | Quick display without calculation |
| `uploaded_by` | string | Audit trail / accountability |
| `tags` | array[string] | Custom search/organization |
| `checksum_verified` | boolean | Quality assurance flag |
| `processing_duration_ms` | number | Performance metrics |

#### Example New Schema
```json
{
  "id": "4b77e210",
  "dataset_name": "iowa_survey",
  "filename": "iowa.laz",
  "object_name": "uploads/iowa_survey/4b77e210/iowa.laz",
  "size": 7207684,
  "file_extension": "laz",
  "file_hash": "sha256:abc123def456...",
  "file_size_mb": 6.87,
  "uploaded_by": "user@example.com",
  "tags": ["2026-q2", "region-midwest"],
  "status": "completed",
  "created_at": "2026-04-20T15:06:46.441Z",
  "updated_at": "2026-04-20T15:12:28.160Z",
  "point_count": 1234567,
  "node_count": 128,
  "processing_duration_ms": 345000,
  "checksum_verified": true
}
```

---

### 3. Fix ID Consistency

#### Problem
- API generates: `file_id = uuid4()[:8]`
- Repository generates: `dataset.id = uuid4()[:8]`
- MinIO path uses API ID: `uploads/iowa_survey/{api_id}/iowa.laz`
- MongoDB stores repository ID: `dataset.id = {repo_id}`
- **Result**: Same upload has two different IDs

#### Solution
1. Generate ID once in API
2. Pass to repository instead of auto-generating
3. MinIO path and MongoDB `id` will always match

#### Code Change
```python
# Before (mismatch)
file_id = str(uuid.uuid4())[:8]  # Use for MinIO
object_name = f"uploads/{dataset_name}/{file_id}/{file.filename}"
dataset = await dataset_repo.create(dataset_name, filename, object_name, size)
# Inside repo.create(), another ID is generated

# After (consistent)
file_id = str(uuid.uuid4())[:8]
object_name = f"uploads/{dataset_name}/{file_id}/{file.filename}"
dataset = await dataset_repo.create(file_id, dataset_name, filename, object_name, size)
# Repository uses passed file_id instead of generating new one
```

---

### 4. New Repository Query Methods

Add these methods to `DatasetRepository` for faster retrieval:

```python
async def get_by_dataset_and_filename(self, dataset_name: str, filename: str) -> Optional[Dataset]
    """Find specific file in a dataset group."""

async def list_by_status(self, status: str) -> List[Dataset]
    """Find all files with given status (failed, processing, completed)."""

async def list_by_extension(self, dataset_name: str, extension: str) -> List[Dataset]
    """Find all files with extension (.laz, .las) in a dataset."""

async def search_by_tags(self, tags: List[str]) -> List[Dataset]
    """Find all files with any of given tags."""

async def get_by_file_hash(self, file_hash: str) -> Optional[Dataset]
    """Find duplicate by file hash."""

async def list_recent(self, dataset_name: str, days: int = 7) -> List[Dataset]
    """Find files uploaded in last N days."""
```

---

### 5. Index Initialization at Startup

Create a migration/initialization module:

```python
# app/core/mongo_setup.py
async def initialize_indexes(db: AsyncIOMotorDatabase):
    """Create all required indexes on app startup."""
    datasets_collection = db.datasets
    
    await datasets_collection.create_index([("dataset_name", 1)])
    await datasets_collection.create_index([("object_name", 1)], unique=True)
    await datasets_collection.create_index([("dataset_name", 1), ("filename", 1)])
    await datasets_collection.create_index([("status", 1)])
    await datasets_collection.create_index([("dataset_name", 1), ("status", 1), ("created_at", -1)])
    await datasets_collection.create_index([("file_hash", 1)], sparse=True)
    await datasets_collection.create_index([("tags", 1)], sparse=True)
```

---

## Benefits Summary

### Performance
| Query Type | Before | After |
|------------|--------|-------|
| Get all files in group | O(n) scan | O(log n) index lookup |
| Find specific file | O(n) scan | O(log n) index lookup |
| List by status | O(n) scan | O(log n) index lookup |
| Find by hash | N/A (no hash) | O(log n) deduplication check |

### Data Quality
- **Deduplication**: Detect when same file uploaded twice (by hash)
- **Audit trail**: Track who uploaded what and when
- **Versioning**: detect file changes via hash comparison
- **Validation**: `checksum_verified` flag

### Developer Experience
- **Debugging**: Single consistent ID throughout system
- **Tracing**: Follow a file from MinIO → MongoDB → Processing
- **Filtering**: Rich query capabilities (by tag, extension, date range)
- **Metrics**: Track processing time, success rate per uploader

### Scalability
- Works with thousands of files without performance degradation
- Ready for future features (bulk operations, advanced search, analytics)

---

## Implementation Checklist

- [ ] Add new fields to Dataset model
- [ ] Update repository.create() to accept dataset_id
- [ ] Update API upload endpoint to pass dataset_id to repository
- [ ] Add new repository query methods
- [ ] Create mongo_setup.py with index initialization
- [ ] Call index initialization in app startup
- [ ] Write tests for new query methods
- [ ] Update API endpoints to use new methods (optional search endpoints)

---

## Files to Modify

1. `project/app/models/dataset.py` - Add new fields
2. `project/app/repositories/__init__.py` - Add indexes and methods
3. `project/app/api/datasets.py` - Pass dataset_id to repository
4. `project/app/core/mongo_client.py` or new `project/app/core/mongo_setup.py` - Index initialization

---

## Migration Strategy for Existing Data

For files already in MongoDB without new fields:
1. Backfill `file_extension` from `filename`
2. Backfill `file_size_mb` from `size`
3. Set `uploaded_by` to "unknown" if missing
4. Calculate `file_hash` for existing files (optional, one-time operation)
5. Indexes will be created automatically on app startup
