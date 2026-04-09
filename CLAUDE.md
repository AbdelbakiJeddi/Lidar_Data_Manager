# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
FastAPI service integrated with MinIO for streaming upload/download of large files (specifically targeted for LiDAR LAS/LAZ files) and JSON metadata storage.

## Architecture
- **API Layer**: FastAPI (`app/main.py`) providing endpoints for file and JSON operations.
- **Storage Layer**: MinIO (S3-compatible object storage), interfaced via `app/minio_client.py`.
- **Containerization**: Docker Compose orchestrates both the FastAPI application and the MinIO server.
- **Data Flow**: Files are streamed directly between the client and MinIO to handle large point cloud data without exhausting memory.

## Common Commands

### Development & Deployment
- **Start everything**: `docker compose up --build`
- **Stop everything**: `docker compose down`
- **Local run (Python only)**: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` (requires `pip install -r requirements.txt`)

### Infrastructure Access
- **MinIO Console**: `http://localhost:9001` (Admin: `minioadmin`/`minioadmin`)
- **API Swagger Docs**: `http://localhost:8000/docs`
- **API Base URL**: `http://localhost:8000`

## Key Implementation Details
- **Streaming**: `upload_file` uses `client.put_object` with the file stream directly. `download_file` returns a `StreamingResponse`.
- **Environment Variables**: MinIO configuration (endpoint, keys, bucket) is managed via environment variables defined in `docker-compose.yml`.
- **Bucket Management**: The application ensures the target bucket exists on startup via `ensure_bucket`.
