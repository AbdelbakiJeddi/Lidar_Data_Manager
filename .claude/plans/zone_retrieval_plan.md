# Zone Retrieval Feature - Implementation Plan

## User Story
User selects a bounding box (AOI) → Server retrieves all intersecting octree nodes → Merges them → Returns the zone point cloud.

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Client sends   │     │  Server queries  │     │  Server merges  │
│  bbox (AOI)     │────▶│  nodes in bbox   │────▶│  node LAZ files │
│  POST /query    │     │  from MongoDB    │     │  via PDAL       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                        │
         │                       │                        │
         ▼                       ▼                        ▼
  { min_x, min_y, min_z,   [node_0, node_3,        StreamingResponse
    max_x, max_y, max_z }   node_5, ...]            with merged.laz
```

---

## Step 1: Add Spatial Methods to `BoundingBox`

**File:** `app/models/bounding_box.py`

Add two methods:

```python
def intersects(self, other: "BoundingBox") -> bool:
    """Check if this bounding box intersects with another."""

def contains(self, other: "BoundingBox") -> bool:
    """Check if this bounding box fully contains another."""
```

**Why:** Needed for server-side validation and client-side filtering logic.

---

## Step 2: Add Repository Query Method

**File:** `app/repositories/node_repository.py`

Add method:

```python
async def get_nodes_in_bbox(
    self,
    dataset_id: str,
    bbox: BoundingBox
) -> List[Dict[str, Any]]:
    """Get all nodes whose bbox intersects with the given AOI."""
```

**MongoDB Query:**
```python
{
    "dataset_id": dataset_id,
    "bbox.max_x": {"$gt": bbox.min_x},
    "bbox.min_x": {"$lt": bbox.max_x},
    "bbox.max_y": {"$gt": bbox.min_y},
    "bbox.min_y": {"$lt": bbox.max_y},
    "bbox.max_z": {"$gt": bbox.min_z},
    "bbox.min_z": {"$lt": bbox.max_z},
}
```

**Index recommendation:**
```python
await db.octree_nodes.create_index([
    ("dataset_id", 1),
    ("bbox.min_x", 1),
    ("bbox.max_x", 1),
    ("bbox.min_y", 1),
    ("bbox.max_y", 1),
    ("bbox.min_z", 1),
    ("bbox.max_z", 1),
])
```

---

## Step 3: Add API Endpoints

**File:** `app/api/nodes.py`

### Endpoint 1: Query nodes by bbox (metadata only)

```python
@router.post("/{dataset_id}/query-by-bbox")
async def query_nodes_by_bbox(
    dataset_id: str,
    bbox: BoundingBox,
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """
    Get all nodes intersecting a bounding box.
    
    Request body:
    {
        "min_x": ..., "max_x": ...,
        "min_y": ..., "max_y": ...,
        "min_z": ..., "max_z": ...
    }
    
    Response:
    {
        "nodes": [...],
        "count": 5
    }
    """
```

### Endpoint 2: Download merged zone

```python
@router.post("/{dataset_id}/download-zone")
async def download_zone(
    dataset_id: str,
    bbox: BoundingBox,
    db: AsyncIOMotorDatabase = Depends(get_db),
    minio_client: Minio = Depends(get_minio)
) -> StreamingResponse:
    """
    Download merged point cloud for all nodes in a zone.
    
    - Queries nodes intersecting bbox
    - Downloads each node's LAZ from MinIO to temp
    - Merges via PDALProcessor.merge_files()
    - Streams merged result
    - Cleans up temp files
    """
```

---

## Step 4: Add Service Method (Optional)

**File:** `app/services/octree_zone_service.py` (new)

Extract zone logic into service:

```python
class OctreeZoneService:
    async def get_nodes_in_bbox(dataset_id: str, bbox: BoundingBox) -> List[OctreeNode]
    async def merge_nodes_in_bbox(dataset_id: str, bbox: BoundingBox) -> str  # returns temp file path
```

**Decision:** Keep it simple for now. Inline in API route. Refactor if logic grows.

---

## Step 5: Update MongoDB Indexes

**File:** `app/core/mongo_client.py`

Add compound index on bbox fields for faster spatial queries.

---

## Testing Checklist

- [ ] Query with bbox that intersects 0 nodes → empty list
- [ ] Query with bbox that intersects 1 node → single node
- [ ] Query with bbox that intersects multiple nodes → all returned
- [ ] Download zone returns valid merged LAZ
- [ ] Temp files cleaned up after download
- [ ] Error handling: invalid bbox (min > max)
- [ ] Error handling: dataset not found

---

## Files to Modify

| File | Change |
|------|--------|
| `app/models/bounding_box.py` | Add `intersects()`, `contains()` |
| `app/repositories/node_repository.py` | Add `get_nodes_in_bbox()` |
| `app/api/nodes.py` | Add 2 new endpoints |
| `app/core/mongo_client.py` | Add bbox index (optional optimization) |

---

## API Usage Example

### 1. Query which nodes are in zone
```bash
curl -X POST http://localhost:8000/lidar/nodes/dataset123/query-by-bbox \
  -H "Content-Type: application/json" \
  -d '{
    "min_x": 500000, "max_x": 500100,
    "min_y": 4500000, "max_y": 4500100,
    "min_z": 100, "max_z": 200
  }'
```

### 2. Download merged zone
```bash
curl -X POST http://localhost:8000/lidar/nodes/dataset123/download-zone \
  -H "Content-Type: application/json" \
  -d '{
    "min_x": 500000, "max_x": 500100,
    "min_y": 4500000, "max_y": 4500100,
    "min_z": 100, "max_z": 200
  }' \
  --output zone.laz
```

---

## Trade-offs Considered

| Approach | Pro | Con |
|----------|-----|-----|
| Server-side merge | Single download for user | Server CPU/bandwidth cost |
| Client-side merge | Server lightweight | Client downloads many files |
| Return node list only | Simplest | User must merge manually |

**Decision:** Provide both endpoints. User chooses: metadata only OR merged download.

---

## Next Steps After Approval

1. Implement Step 1-3
2. Test with existing dataset
3. Add error handling
4. Optional: Add bbox index for performance
