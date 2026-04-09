# FastAPI + MinIO Starter

This project demonstrates a simple FastAPI service that uploads and retrieves files and JSON data from MinIO.

## Setup

1. Start MinIO and the API service:

   docker compose up --build

2. Open the MinIO console at:

   http://localhost:9001

   Access key: `minioadmin`
   Secret key: `minioadmin`

3. Access the API at:

   http://localhost:8000

4. Swagger docs:

   http://localhost:8000/docs

## Endpoints

- `GET /health`
- `POST /upload-file` - multipart file upload (supports large files via streaming)
- `GET /download-file/{object_name}` - download file with proper headers
- `GET /file-info/{object_name}` - get file metadata (size, type, etc.)
- `POST /store-json` - store JSON payload
- `GET /retrieve-json/{object_name}`
- `GET /list-objects`

## Customization

Change MinIO settings in `docker-compose.yml` or via environment variables:

- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_BUCKET`

## Notes

- Default bucket: `fastapi-bucket`
- FastAPI uses env vars from `docker-compose.yml`
- Supports large file uploads (tested with 650MB+ LAS files) via streaming
- For large downloads, use curl or increase Postman's response size limit
- If you want a local Python-only run, install `requirements.txt` and run:
  - `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
