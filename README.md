# LiDAR Data Manager

FastAPI service for managing LiDAR point cloud data with SPSLiDAR octree-based hierarchical storage.

## Overview

This service provides:
- **Upload**: Stream LAZ/LAS files to MinIO object storage
- **Process**: Build hierarchical octree structures using PDAL with SPSLiDAR sampling algorithm
- **Store**: Raw data in MinIO, metadata in MongoDB
- **Serve**: Query and download octree nodes via REST API
- **Visualize**: Potree-compatible output for web-based point cloud viewing

## Quick Start

```bash
# Start all services (MinIO, MongoDB, FastAPI)
docker compose up --build

# Access services:
# - API:        http://localhost:8000
# - API Docs:   http://localhost:8000/docs
# - MinIO:      http://localhost:9001 (minioadmin/minioadmin)
# - MongoDB UI: http://localhost:8081 (admin/admin)
```

## Architecture

```

┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Client    │──────▶│   FastAPI   │──────▶│    MinIO    │
│             │      │             │      │  (raw LAZ)  │
└─────────────┘      │             │      └─────────────┘
                     │             │      ┌─────────────┐
                     │             │──────▶│   MongoDB   │
                     │             │      │  (metadata) │
                     │             │      └─────────────┘
                     └─────────────┘
                            │
                     ┌──────┴──────┐
                    │     PDAL      │
                    │   (native)    │
                     └─────────────┘
```

## API Usage

### Upload a LiDAR File

```bash
curl -X POST "http://localhost:8000/lidar/upload" \
  -F "file=@terrain.laz" \
  -F "dataset_name=my_dataset"

# Response:
# {"dataset_id": "abc123", "filename": "terrain.laz", "dataset_name": "my_dataset"}
```

### Process (Build Octree)

```bash
curl -X POST "http://localhost:8000/lidar/process/abc123" \
  -H "Content-Type: application/json" \
  -d '{"max_depth": 3, "point_threshold": 10000}'
```

### Get Nodes

```bash
# All nodes
curl "http://localhost:8000/lidar/datasets/abc123/nodes"

# Filter by depth
curl "http://localhost:8000/lidar/datasets/abc123/nodes?depth=2"

# Download specific node
curl "http://localhost:8000/lidar/nodes/abc123/0/download" -o node_0.laz
```

### Get Dataset Bounds (for 2D map footprint)

```bash
curl "http://localhost:8000/lidar/datasets/abc123/bounds"

# Response:
# {"dataset_id": "abc123", "bbox": [minx, miny, maxx, maxy]}
```

### Query by Bounding Box (for AOI selection)

```bash
curl -X POST "http://localhost:8000/lidar/datasets/abc123/query" \
  -H "Content-Type: application/json" \
  -d '{"bbox": [minx, miny, maxx, maxy], "max_nodes": 150}'

# Response:
# {
#   "dataset_id": "abc123",
#   "selected_nodes": 42,
#   "nodes": [{"node_id": "0", "bbox": [...], "url": "https://..."}]
# }
```

### Health Check

```bash
curl http://localhost:8000/health
```

## Project Structure

```
app/
├── api/
│   ├── __init__.py          # Router exports
│   ├── dependencies.py      # FastAPI DI (DB, MinIO clients)
│   ├── datasets.py          # Dataset endpoints + bounds + query
│   ├── nodes.py             # Node endpoints
│   └── health.py            # Health check endpoint
├── models/
│   ├── __init__.py          # Pydantic models
│   ├── bounding_box.py      # BoundingBox with octant split
│   └── dataset.py           # Dataset, OctreeNode models
├── repositories/
│   └── __init__.py          # MongoDB repositories (DatasetRepo, OctreeNodeRepo)
├── core/
│   ├── minio_client.py      # MinIO client + helpers
│   ├── mongo_client.py      # MongoDB client + indexes
│   └── settings.py          # Configuration
└── services/
    ├── octree_builder.py    # SPSLiDAR Fast Recursive Octree algorithm
    └── pdal_processor.py    # PDAL CLI pipeline wrapper
```

## Configuration

Environment variables (set in `docker-compose.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ENDPOINT` | `minio:9000` | MinIO server address |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `MONGO_URI` | `mongodb://root:rootpassword@mongodb:27017` | MongoDB connection |
| `PDAL_BIN` | `pdal` | PDAL binary path |

## Data Flow

1. **Upload** → MinIO (`lidar-raw` bucket) + MongoDB (dataset metadata)
2. **Process** → Background task reads from MinIO, builds octree with SPSLiDAR algorithm
3. **Store** → Nodes saved to MinIO (`lidar-processed` bucket) + MongoDB
4. **Query** → API queries MongoDB metadata, returns presigned URLs from MinIO
5. **Visualize** → Potree loads COPC/LAZ data via presigned URLs

## Development

```bash
# Start infrastructure only
docker compose up minio mongodb mongo-express -d

# Local development
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## SPSLiDAR Algorithm

The octree uses **SPSLiDAR Fast Recursive sampling**:
- At each node: sample every Nth point → stays at current node
- Remainder points → partitioned into 8 spatial octants → recursed
- Each point appears in exactly **one** node (zero duplication)
- All I/O handled by PDAL CLI pipelines (C++ engine)

## Testing

### Automated Tests

```bash
# Run pytest suite
pytest tests/

# With coverage
pytest --cov=app tests/

# Specific test file
pytest tests/test_octree.py -v
```

### Manual Testing

```bash
# 1. Start services
docker compose up --build

# 2. Health check
curl http://localhost:8000/health

# 3. Upload file
curl -X POST "http://localhost:8000/lidar/upload" \
  -F "file=@test.laz" \
  -F "dataset_name=test_dataset"

# 4. Build octree
curl -X POST "http://localhost:8000/lidar/process/{dataset_id}" \
  -H "Content-Type: application/json" \
  -d '{"max_depth": 8, "point_threshold": 10000}'

# 5. Query nodes
curl "http://localhost:8000/lidar/datasets/{dataset_id}/nodes"

# 6. Download node
curl "http://localhost:8000/lidar/nodes/{dataset_id}/0/download" -o node.laz
```

### Cleanup Test Data

```bash
# Remove test datasets
python scripts/cleanup_data.py
```

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for full testing guide.

## Tech Stack

- **API**: FastAPI + Pydantic
- **Storage**: MinIO (S3-compatible)
- **Database**: MongoDB + Motor (async)
- **Processing**: PDAL 2.6+ (native CLI pipelines)
- **Runtime**: Python 3.12, Docker

## Frontend Integration

A single-page web viewer is planned for v2:
- Upload + process from browser
- 2D map footprint display
- Draw/select area of interest
- Load selected nodes in Potree viewer

See [docs/frontend_potree_task.md](docs/frontend_potree_task.md) for implementation plan.

## Troubleshooting

**Container won't start:**

```bash
docker compose logs web
docker compose logs minio
```

**MinIO connection issues:**

```bash
# Check MinIO is ready
docker compose exec web curl http://minio:9000/minio/health/live
```

**MongoDB connection:**

```bash
docker compose exec mongodb mongosh -u root -p rootpassword --eval "db.adminCommand('ping')"
```

**PDAL not available:**
```bash
docker compose exec web pdal --version
```

## License

Internal project - See LICENSE file

## See Also

- [PROJECT_STATUS.md](PROJECT_STATUS.md) - Full status, roadmap, and testing guide
- [docs/frontend_potree_task.md](docs/frontend_potree_task.md) - Frontend integration plan
- [docs/octree_metadata_extraction.md](docs/octree_metadata_extraction.md) - Metadata extraction details
