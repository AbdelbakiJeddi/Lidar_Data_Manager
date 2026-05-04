# LiDAR Data Manager

FastAPI service for managing LiDAR point cloud data with flat 2D tile storage and a premium React-based spatial interface.

## Overview

This project provides a complete end-to-end solution for LiDAR data management:
- **Upload**: Stream LAZ/LAS files to MinIO object storage.
- **Process**: Split into a flat 2D grid of tiles using PDAL and convert to COPC.
- **Spatial Intelligence**: Automated geographic boundary extraction and on-the-fly coordinate reprojection (UTM/Lambert/etc. to WGS84).
- **Interactive Selection**: Premium web interface for selecting and extracting custom zones via free-form polygons.
- **Store**: Raw data in MinIO, metadata in MongoDB.
- **Serve**: Query and download tiles or custom spatial zones via REST API.

## Quick Start

```bash
# Start all services (MinIO, MongoDB, FastAPI, Frontend)
docker compose up --build

# Access services:
# - Web Interface: http://localhost:5173
# - API Gateway:   http://localhost:8000
# - API Docs:      http://localhost:8000/docs
# - MinIO UI:      http://localhost:9001 (minioadmin/minioadmin)
# - MongoDB UI:    http://localhost:8081 (admin/admin)
```

## Architecture

```

┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  React UI   │◀────▶│   FastAPI   │──────▶│    MinIO    │
│   (Vite)    │      │   Gateway   │      │  (raw LAZ)  │
└─────────────┘      └──────┬──────┘      └─────────────┘
                            │             ┌─────────────┐
                     ┌──────┴──────┐      │   MongoDB   │
                     │    PDAL     │◀────▶│  (metadata) │
                     │  + pyproj   │      └─────────────┘
                     └─────────────┘
```

## Key Features (Latest Progress)

### 🗺️ Spatial Intelligence
- **Automated Metadata Extraction**: Uses `pdal info --boundary` to calculate geographic footprints automatically.
- **On-the-fly Reprojection**: Integrated `pyproj` in the backend. User-drawn Lat/Long coordinates on the map are dynamically reprojected to the dataset's native SRS before cropping.
- **SRS Auto-Detection**: Automatically identifies coordinate systems (e.g., UTM Zone 16N) and provides an override UI for files missing SRS metadata.

### ✒️ Premium Web Interface
- **Interactive Zone Selector**: A professional split-pane modal featuring a dark-mode Leaflet map (CartoDB).
- **Free-form Polygon Drawing**: Users can click to place vertices and construct any arbitrary shape. Clicking the start point closes the polygon.
- **Real-time Feedback**: Side panel displays native bounding boxes, selection coordinates, and elevation filters.
- **Glassmorphism Design**: Modern UI with blurred panels, micro-animations, and a responsive layout using Outfit/Inter typography.

## API Usage (Spatial)

### Extract Custom Zone (Polygon)
```bash
# Extract a custom shape by providing geographic vertices
curl -X POST "http://localhost:8000/lidar/tiles/{dataset_id}/zone" \
  -H "Content-Type: application/json" \
  -d '{
    "coordinates": [[-86.15, 39.76], [-86.11, 39.76], [-86.13, 39.79]],
    "min_z": 100,
    "max_z": 500
  }' -o custom_zone.laz
```

### Get Dataset Info (including Geo-Bounds)
```bash
curl "http://localhost:8000/lidar/datasets/{id}/info"
# Returns: { "geographic_bbox": { "min_x": ..., "min_y": ... }, "srs_wkt": "..." }
```

## Project Structure

```
.
├── app/                  # FastAPI Backend
│   ├── api/              # API Endpoints (datasets, nodes, health)
│   ├── core/             # Database & MinIO clients
│   ├── models/           # Pydantic & MongoDB models
│   ├── services/         # PDAL Processor, Tile Manager
│   └── main.py           # App entry point
├── frontend/             # React Frontend
│   ├── src/
│   │   ├── components/   # ZoneSelector, DatasetList, etc.
│   │   ├── api.js        # Axios client
│   │   └── App.jsx       # Main layout
│   └── index.css         # Modern design tokens
├── docker-compose.yml    # Orchestration
└── requirements.txt      # Backend dependencies (now includes pyproj)
```

## Tech Stack

- **Frontend**: Vite, React, Leaflet, Lucide Icons, Axios.
- **Backend**: FastAPI, Pydantic, Motor (MongoDB).
- **Processing**: PDAL 2.6+ (Native pipelines), `pyproj` (Geospatial transformations).
- **Storage**: MinIO (S3-compatible object storage).
- **Database**: MongoDB (Metadata persistence).

## Development Progress

| Feature | Status |
|---------|--------|
| Multi-file Upload | ✅ Complete |
| Flat 2D Tiling | ✅ Complete |
| Geographic Centering | ✅ Complete |
| Rectangular Selection | ✅ Complete |
| Free-form Polygon | ✅ Complete |
| 3D Visualization (Potree) | 🔄 In Progress |

## Troubleshooting

**Coordinates not showing on map:**
Ensure the file has an SRS. If not, use the **"Fix SRS"** tool in the Zone Selector sidebar to provide the EPSG code (e.g., `EPSG:32631`).

**Container errors:**
If you recently added `pyproj`, run `docker compose up --build` to ensure the new dependency is installed in the container environment.

## License
Internal project - See LICENSE file
