# LiDAR Data Manager - Project Status & Roadmap

**Last Updated:** 2026-04-16  
**Status:** MVP Complete - Core Architecture Implemented

---

## Current Progress

### ✅ Completed

| Component | Status | Notes |
|-----------|--------|-------|
| **Architecture** | Complete | FastAPI + MinIO + MongoDB + LasTools |
| **Folder Structure** | Complete | Organized into models/, repositories/, api/, services/ |
| **File Upload** | Complete | Stream upload to MinIO `lidar-raw` bucket |
| **Octree Processing** | Complete | Recursive subdivision with LasTools via Wine |
| **Metadata Storage** | Complete | MongoDB with async motor client |
| **Node Storage** | Complete | LAZ nodes in `lidar-processed` bucket |
| **API Endpoints** | Complete | Upload, process, query, download endpoints |
| **Health Checks** | Complete | MinIO + MongoDB health endpoints |

### Project Structure

```
project/
├── app/
│   ├── api/
│   │   ├── __init__.py          # Router exports
│   │   ├── dependencies.py      # FastAPI DI (DB, MinIO clients)
│   │   ├── datasets.py          # Dataset endpoints
│   │   ├── nodes.py             # Node endpoints
│   │   └── health.py            # Health check endpoint
│   ├── models/
│   │   └── __init__.py          # Pydantic models (Dataset, OctreeNode, BoundingBox)
│   ├── repositories/
│   │   └── __init__.py          # MongoDB repositories (DatasetRepo, OctreeNodeRepo)
│   ├── core/
│   │   ├── minio_client.py      # MinIO client + helpers
│   │   └── mongo_client.py      # MongoDB client + indexes
│   ├── services/
│   │   ├── octree_builder.py    # Octree processing logic
│   │   ├── las_tools_processor.py # LasTools wrapper
│   │   └── lidar_processor.py   # Additional processing
│   └── main.py                  # FastAPI app + router registration
├── docker-compose.yml           # Services: MinIO, MongoDB, FastAPI
├── Dockerfile                   # FastAPI + LasTools via Wine
└── requirements.txt             # Python dependencies
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/lidar/upload` | Upload LAZ/LAS file |
| `GET` | `/lidar/datasets` | List all datasets |
| `GET` | `/lidar/datasets/{id}` | Get dataset details |
| `POST` | `/lidar/process/{id}` | Start octree processing |
| `GET` | `/lidar/datasets/{id}/nodes` | Get dataset nodes (opt: `?depth=N`) |
| `GET` | `/lidar/datasets/{id}/info` | Get LAZ file metadata (LasTools) |
| `GET` | `/lidar/nodes/{id}/{node_id}` | Get node metadata |
| `GET` | `/lidar/nodes/{id}/{node_id}/download` | Download node LAZ file |

---

## Missing / TODO

### High Priority

| Feature | Description | Impact |
|---------|-------------|--------|
| **Spatial Queries** | Query nodes by bounding box intersection | Essential for visualization |
| **Authentication** | JWT/API key based auth | Production requirement |
| **Rate Limiting** | Prevent abuse on expensive operations | Stability |
| **Error Handling** | Retry logic for MinIO/MongoDB failures | Reliability |
| **Streaming Download** | True streaming for large node files | Performance |

### Medium Priority

| Feature | Description | Impact |
|---------|-------------|--------|
| **Celery/RQ** | Replace BackgroundTasks with proper task queue | Scalability |
| **Point Cloud Visualization** | Potree-compatible output or direct viewer | Usability |
| **SRS Handling** | Coordinate system transformation support | Data compatibility |
| **Progress Tracking** | WebSocket or SSE for processing progress | UX |
| **File Validation** | LAZ format validation before processing | Data integrity |

### Low Priority

| Feature | Description | Impact |
|---------|-------------|--------|
| **Multi-file Upload** | Batch upload multiple LAZ files | Convenience |
| **Compression Options** | Configurable LAZ compression levels | Storage optimization |
| **Metadata Export** | Export to CSV/JSON for analysis | Analytics |
| **Admin Dashboard** | Web UI for monitoring jobs | Operations |

---

## Testing Strategy

### Manual Testing (Current)

```bash
# 1. Start services
docker compose up --build

# 2. Health check
curl http://localhost:8000/health

# 3. Upload test file
curl -X POST "http://localhost:8000/lidar/upload" \
  -F "file=@/path/to/test.laz"

# 4. Process (adjust thresholds for file size)
curl -X POST "http://localhost:8000/lidar/process/{dataset_id}" \
  -H "Content-Type: application/json" \
  -d '{"max_depth": 3, "point_threshold": 10000}'

# 5. Check nodes
curl "http://localhost:8000/lidar/datasets/{dataset_id}/nodes"

# 6. Download a node
curl "http://localhost:8000/lidar/nodes/{dataset_id}/{node_id}/download" \
  -o node.laz
```

### Automated Testing (TODO)

```bash
# Run all tests
pytest tests/

# Coverage report
pytest --cov=app tests/

# Integration tests
docker compose -f docker-compose.yml -f docker-compose.test.yml up --build
```

#### Required Test Files

Create `/tests/` directory with:

| File | Purpose |
|------|---------|
| `conftest.py` | Pytest fixtures (DB, MinIO mocks) |
| `test_upload.py` | File upload tests |
| `test_processing.py` | Octree processing tests |
| `test_queries.py` | API endpoint tests |
| `test_integration.py` | End-to-end workflow |

---

## Environment Setup

### Development

```bash
# Clone and setup
cd project/

# Start infrastructure
docker compose up minio mongodb mongo-express

# Local development (requires Python 3.12+)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Considerations

- Use proper secrets management (not env vars in compose)
- Enable MongoDB authentication
- Configure MinIO HTTPS
- Add reverse proxy (nginx/traefik)
- Set up log aggregation
- Configure monitoring (Prometheus/Grafana)

---

## Known Issues

1. **LasTools via Wine** - Slow on Linux; consider native PDAL migration
2. **In-memory job tracking** - Lost on restart (acceptable for MVP)
3. **No retry logic** - Network failures during processing can leave dataset in "processing" state
4. **Large file handling** - No chunked upload resumption

---

## Next Sprint Suggestions

### Sprint 1: Stability
1. Add comprehensive error handling
2. Implement spatial query endpoints
3. Add basic authentication

### Sprint 2: Performance
1. Replace LasTools with PDAL
2. Add Redis for caching
3. Implement true streaming downloads

### Sprint 3: Features
1. WebSocket progress updates
2. Visualization export (Potree)
3. Batch processing API

---

## Team Onboarding

### New Developer Setup

1. Install Docker & Docker Compose
2. Clone repository
3. Run `docker compose up --build`
4. Access Swagger at http://localhost:8000/docs
5. Review code structure in `app/`

### Code Style

- Follow PEP 8
- Use type hints
- Document functions with docstrings
- Keep functions under 50 lines where possible
- Use dependency injection (see `app/api/dependencies.py`)

### Pull Request Process

1. Branch from `main`
2. Write tests for new features
3. Update this document if adding features
4. Request review from team lead
5. Merge after CI passes

---

## Resources

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Motor (MongoDB Async)](https://motor.readthedocs.io/)
- [MinIO Python SDK](https://docs.min.io/docs/python-client-api-reference.html)
- [LasTools Documentation](https://rapidlasso.de/products/lastools/)
- [LAZ Specification](https://laszip.org/)

---

**Questions?** Check the Swagger docs at `/docs` or ask in team Slack.
