# LiDAR Data Manager Web Interface Implementation Plan

This plan outlines the steps to build a web interface for the LiDAR Data Manager, enabling users to upload datasets, visualize them on a map, and query specific areas for 3D visualization using Potree.

## User Review Required

> [!IMPORTANT]
> **Potree Integration**: Potree requires direct access to LAS/LAZ files. We will need to ensure MinIO CORS settings are correctly applied to allow `Range` requests from the browser.
> **Frontend Stack**: I propose using **Vite + Vanilla JS** for a clean, modern setup that remains "simple" as requested, while providing a fast development experience.

## Proposed Changes

---

### Phase 1: Backend Enhancements

We need to add spatial query capabilities and ensure the frontend can securely access processed nodes.

#### [MODIFY] [datasets.py](file:///home/abok/Desktop/pcd_ws/project/app/api/datasets.py)
- Add `GET /lidar/datasets/{dataset_id}/bounds` endpoint.
- Add `POST /lidar/datasets/{dataset_id}/query` endpoint.
    - Logic: Filter `OctreeNode` records by BBox intersection.
    - Generate presigned URLs for each matching node.

#### [MODIFY] [minio_client.py](file:///home/abok/Desktop/pcd_ws/project/app/core/minio_client.py)
- Add a helper function to set CORS configuration on the `lidar-processed` bucket.

---

### Phase 2: Frontend - Core Layout & Upload

A single-page application with a three-panel layout.

#### [NEW] `web-ui/` (Vite Project)
- `index.html`: Main structure (Left: Sidebar, Center: Map, Right: Viewer).
- `style.css`: Modern layout with glassmorphism and smooth transitions.
- `main.js`: Main entry point and state management.

#### Features
- **Upload Form**: Name input + file picker.
- **Dataset List**: Shows status (uploaded, processing, completed, failed).
- **Polling**: Automatically poll status for processing datasets.

---

### Phase 3: Frontend - 2D Map & AOI

Integrating Leaflet for spatial context.

#### Features
- **Leaflet Map**: OpenStreetMap base layer.
- **Dataset Bounds**: Fetch bounds from backend and display as a rectangle.
- **AOI Selection**: Tool to draw a rectangle on the map to define the Area of Interest (AOI).

---

### Phase 4: Frontend - Potree Integration

High-performance 3D point cloud visualization.

#### Features
- **Potree Viewer**: Embedded in the right panel.
- **Query Integration**: When AOI is drawn, send BBox to `/query` endpoint.
- **Node Loading**: Fetch LAS/LAZ nodes from presigned URLs and add them to the Potree scene.

---

## Verification Plan

### Automated Tests
- `pytest`: Add tests for the new `bounds` and `query` endpoints.
- Browser tests (manual/subagent):
    1. Upload a sample LAS file.
    2. Wait for processing.
    3. Verify bounds appear on map.
    4. Draw AOI and verify nodes load in Potree.

### Manual Verification
- Verify that MinIO CORS headers are correctly returned in the browser's Network tab (check for `Access-Control-Allow-Origin` and `Range` header support).
