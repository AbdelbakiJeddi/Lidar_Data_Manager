# Web Interface Implementation Task

## Objective
Add web interface for LiDAR dataset upload, map visualization, and point cloud retrieval from MinIO.

## Context
Existing backend: FastAPI + MinIO + MongoDB + PDAL octree processor.
Existing frontend doc: `docs/frontend_potree_task.md`.

## Scope
Single-page app. No EPT. COPC for visualization.

---

## Backend Tasks

### 1. Add bounds endpoint
`GET /lidar/datasets/{dataset_id}/bounds`

Returns:
```json
{
  "dataset_id": "...",
  "bbox": [minx, miny, maxx, maxy]
}
```

### 2. Add bbox query endpoint
`POST /lidar/datasets/{dataset_id}/query`

Request:
```json
{
  "bbox": [minx, miny, maxx, maxy],
  "max_nodes": 150
}
```

Response:
```json
{
  "dataset_id": "...",
  "selected_nodes": 42,
  "nodes": [
    {
      "node_id": "...",
      "bbox": [minx, miny, maxx, maxy],
      "url": "https://... (presigned, 1h)"
    }
  ]
}
```

Implementation:
- Filter `OctreeNode` records where bbox intersects AOI
- Generate presigned GET URLs via MinIO client
- Cap results at `max_nodes`

### 3. MinIO CORS config
Enable GET/HEAD + Range requests for visualization access.

---

## Frontend Tasks

### 4. Single-page layout
```
Left panel        |  Center panel (map)      |  Right panel (viewer)
- Upload form     |  - Dataset bbox rect     |  - Potree canvas
- Process button  |  - AOI drawable rect      |  - Node count info
- Status tracker  |  - Query button          |
```

### 5. Upload flow
- Form: `dataset_name` (string) + `file` (.las/.laz)
- POST `/lidar/upload` → store `dataset_id`
- POST `/lidar/process/{dataset_id}` → poll `/lidar/datasets/{dataset_id}` until completed

### 6. 2D map
- Display uploaded dataset bbox as read-only rectangle (e.g. Leaflet + OSM)
- Allow user to draw AOI rectangle
- Send AOI bbox on query

### 7. Point cloud retrieval
- POST AOI bbox to `/lidar/datasets/{dataset_id}/query`
- Receive node list with presigned URLs
- Pass URLs to Potree viewer

### 8. Potree viewer integration
- Load COPC or LAS files from presigned URLs
- Fit camera to loaded content

---

## Validation
1. Upload small .las/.laz
2. Process completes without timeout
3. Map shows dataset bbox
4. Draw AOI + query returns matching nodes
5. Potree renders retrieved data

---

## Non-Goals
- No multipage routing
- No advanced polygon editing
- No EPT support
- No multi-user features
