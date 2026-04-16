# LiDAR Data Manager

FastAPI service for managing LiDAR point cloud data with octree-based hierarchical storage.

## Overview

This service provides:
- **Upload**: Stream LAZ/LAS files to MinIO object storage
- **Process**: Build hierarchical octree structures using LasTools
- **Store**: Raw data in MinIO, metadata in MongoDB
- **Serve**: Query and download octree nodes via REST API

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
                     │   LasTools    │
                     │  (via Wine)   │
                     └─────────────┘
```

## API Usage

### Upload a LiDAR File

```bash
curl -X POST "http://localhost:8000/lidar/upload" \
  -F "file=@terrain.laz"

# Response:
# {"dataset_id": "abc123", "filename": "terrain.laz", ...}
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

### Health Check

```bash
curl http://localhost:8000/health
```

## Project Structure

```
app/
├── api/               # FastAPI routes (datasets, nodes, health)
├── models/            # Pydantic data models
├── repositories/      # MongoDB access layer
├── core/              # MinIO & MongoDB clients
└── services/          # Octree processing logic
```

## Configuration

Environment variables (set in `docker-compose.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ENDPOINT` | `minio:9000` | MinIO server address |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `MONGO_URI` | `mongodb://root:rootpassword@mongodb:27017` | MongoDB connection |

## Data Flow

1. **Upload** → MinIO (`lidar-raw` bucket) + MongoDB (dataset metadata)
2. **Process** → Background task reads from MinIO, builds octree
3. **Store** → Nodes saved to MinIO (`lidar-processed` bucket) + MongoDB
4. **Query** → API queries MongoDB metadata, streams from MinIO

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

## Testing

```bash
# Manual test sequence
./test_manual.sh  # (create this script from PROJECT_STATUS.md)

# Or use Python script
cd tests/
python test_integration.py
```

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for full testing guide.

## Tech Stack

- **API**: FastAPI + Pydantic
- **Storage**: MinIO (S3-compatible)
- **Database**: MongoDB + Motor (async)
- **Processing**: LasTools (via Wine)
- **Runtime**: Python 3.12, Docker

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
# Check MongoDB is accepting connections
docker compose exec mongodb mongosh -u root -p rootpassword --eval "db.adminCommand('ping')"
```

## License

Internal project - See LICENSE file

## See Also

- [PROJECT_STATUS.md](PROJECT_STATUS.md) - Full status, roadmap, and testing guide
