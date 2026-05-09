# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Start development environment:**
```bash
# Build and start all services
docker compose up --build

# Start services in background
docker compose up -d --build

# Stop and remove containers
docker compose down
```

**Backend development:**
```bash
# Install backend dependencies (if needed)
pip install -r requirements.txt

# Run tests (if test suite exists)
python -m pytest tests/ -v

# Run FastAPI dev server (for direct development without Docker)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend development:**
```bash
# Install frontend dependencies
cd frontend && npm install

# Start frontend dev server
npm run dev

# Build for production
npm run build
```

**Project maintenance:**
```bash
# View running container logs
docker compose logs -f [service-name]

# Enter backend container for debugging
docker compose exec web bash

# Enter frontend container for debugging
docker compose exec frontend bash

# Prune unused Docker resources
docker system prune -f
```

## Architecture Overview

**System Structure:**
- **Backend (`app/`)**: FastAPI application with async MongoDB driver (Motor)
  - `app/api/`: REST endpoint handlers (`/lidar/*` routes)
  - `app/services/`: Core processing logic (PDALProcessor, TileManager)
  - `app/repositories/`: MongoDB data access layer (DatasetRepository, TileRepository)
  - `app/core/`: Infrastructure (MinIO client, MongoDB connection, settings)
  - `app/main.py`: Application entry point with lifespan context manager

- **Frontend (`frontend/`)**: React + Vite application
  - `src/components/`: UI components (DatasetList, ZoneSelector, DatasetGroupViewer)
  - `src/api.js`: Axios HTTP client for API communication
  - `src/App.jsx`: Main application layout

- **Storage & Database:**
  - **MinIO**: Object storage for raw LAZ/LAS files and processed COPC tiles
    - Buckets: `lidar-raw` (uploaded files), `lidar-processed` (COPC tiles)
  - **MongoDB**: Metadata storage
    - Collections: `datasets` (file metadata), `tiles` (tile grid index)

**Key Workflows:**
1. **Ingestion**: LAZ upload → MinIO → Document creation → Background processing (PDAL tiling → COPC conversion → MinIO storage → Tile metadata)
2. **Query**: User draws bounding box → API queries MongoDB for intersecting tiles → Downloads COPC files → Merges/crops with PDAL → Streams LAZ result

**Important Notes:**
- PDAL 2.6+ is required for COPC support; version differences in bounding box output are handled via `_extract_bbox()` helper
- File uploads use streaming (`length=-1`) to avoid memory issues with large files
- Spatial queries use MongoDB interval-overlap condition on compound index for performance
- Coordinate reprojection uses four-corner method (via pyproj) for accuracy near projection boundaries