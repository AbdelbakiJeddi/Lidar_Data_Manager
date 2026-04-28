# Frontend Integration Plan v2 (Map Selection + Potree)

This version is aligned with the current backend architecture:
- FastAPI routers under /lidar
- MinIO buckets (raw + processed)
- MongoDB dataset and octree node metadata

Goal: keep the workflow simple, efficient, and directly compatible with what already exists.

## Objective
Build one web page where the user can:
1. Upload a LAS/LAZ file
2. View its footprint on a 2D map as a box
3. Draw/select a boundary box of interest
4. Send that boundary to backend
5. Receive data references from server (MinIO-backed)
6. Visualize point cloud data in web viewer

## Scope Decision (v2)
- Use COPC as the default streaming format for frontend visualization.
- Do not implement EPT in v2.
- Keep one-page UI (upload + map + viewer).

## Existing API Reuse
The current backend already provides:
1. POST /lidar/upload: upload LAS/LAZ to raw storage
2. POST /lidar/process/{dataset_id}: start processing
3. GET /lidar/datasets/{dataset_id}: dataset metadata/status
4. GET /lidar/datasets/{dataset_id}/nodes: octree node metadata

v2 should reuse these first, then add only minimal endpoints required for map bounding box flow.

## End-to-End User Flow
1. Upload
- User selects file and dataset name.
- Frontend calls POST /lidar/upload.
- Store returned dataset_id in page state.

2. Process
- Frontend calls POST /lidar/process/{dataset_id} with simple defaults.
- Frontend polls GET /lidar/datasets/{dataset_id} until status is completed.

3. 2D map footprint
- Frontend requests dataset bounds endpoint (new, minimal).
- Map draws one rectangle representing uploaded zone.

4. Boundary selection
- User draws/selects a second rectangle (AOI) on map.
- Frontend sends AOI bbox to backend query endpoint (new, minimal).

5. Data retrieval
- Backend returns matching node references and object URLs (or presigned URLs).
- URLs point to MinIO processed bucket objects.

6. Visualization
- Frontend loads returned COPC/object references in Potree.
- Viewer fits camera to loaded selection.

## Minimal New Backend Endpoints
Add only these two endpoints in v2:

1. GET /lidar/datasets/{dataset_id}/bounds
- Returns dataset bounding box for 2D map overlay.
- Response: { dataset_id, bbox: [minx, miny, maxx, maxy] }

2. POST /lidar/datasets/{dataset_id}/query
- Input: { bbox: [minx, miny, maxx, maxy], max_nodes?: number }
- Backend filters nodes intersecting bbox.
- Response: selected node metadata + downloadable object URLs.

Notes:
- Keep bbox filtering simple and server-side.
- Add max_nodes guard to avoid huge payloads.

## Frontend Page Layout (Single Page)
1. Left panel
- Upload form (dataset_name + file)
- Process button
- Status indicator (uploaded, processing, completed, failed)

2. Center panel
- 2D map
- Uploaded zone rectangle (read-only)
- AOI boundary rectangle (user editable)
- Query button

3. Right panel
- Potree viewer canvas
- Result summary (selected nodes count)

This keeps UX clear and avoids multipage complexity.

## MinIO and Security (Simple but Safe)
1. Keep processed bucket private by default.
2. Backend returns short-lived presigned GET URLs for selected objects.
3. Configure CORS only for frontend origin.
4. Ensure GET and HEAD are allowed; Range requests must work.

## Performance Controls (Low Complexity)
1. AOI query returns capped node count (max_nodes default).
2. Frontend warns user when AOI is too large.
3. Prefer loading subset first, then allow user to widen selection.

## Implementation Plan
1. Backend: Add bounds and bbox query endpoints
- Reuse dataset/node repositories.
- Add simple bbox intersection logic.
- Return presigned URLs from MinIO helper.

2. Frontend: Build one page for upload + map + viewer
- Upload and process via existing endpoints.
- Draw uploaded zone and AOI on 2D map.
- Query selected bbox and load result in Potree.

3. Ops: Configure MinIO CORS
- Allow frontend origin only.
- Verify partial content/range behavior.

4. Validation
- Run complete flow on one sample LAZ:
  upload -> process -> map zone -> draw AOI -> query -> visualize.

## Acceptance Criteria
1. User can upload and process from the same page.
2. Uploaded dataset zone is displayed as a map rectangle.
3. User can draw AOI boundary and submit query.
4. Backend returns only AOI-matching data references.
5. Potree loads returned data and remains responsive.
6. Network inspection confirms partial/range fetch behavior.

## Non-Goals (v2)
1. No advanced editing tools (polygon, multi-select, topology ops).
2. No multi-user collaboration features.
3. No EPT support.
4. No heavy frontend framework migration if not already required.

## Suggested Request/Response Contracts
### Query Request
{
  "bbox": [minx, miny, maxx, maxy],
  "max_nodes": 150
}

### Query Response
{
  "dataset_id": "...",
  "bbox": [minx, miny, maxx, maxy],
  "selected_nodes": 42,
  "nodes": [
    {
      "node_id": "...",
      "bbox": [minx, miny, maxx, maxy],
      "url": "https://..."
    }
  ]
}

This v2 plan keeps your current architecture, adds only two backend endpoints, and delivers the full workflow without unnecessary complexity.
