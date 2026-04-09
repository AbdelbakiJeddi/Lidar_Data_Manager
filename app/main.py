import io
import json
import os
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.minio_client import ensure_bucket, get_minio_client

app = FastAPI(title="FastAPI + MinIO Starter")

MINIO_BUCKET = os.getenv("MINIO_BUCKET", "fastapi-bucket")
client = get_minio_client()
ensure_bucket(client, MINIO_BUCKET)


class JsonPayload(BaseModel):
    key: str
    data: Any


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "bucket": MINIO_BUCKET}


@app.post("/upload-file")
async def upload_file(file: UploadFile = File(...)) -> dict:
    object_name = file.filename
    try:
        # Stream the file directly to MinIO without loading into memory
        client.put_object(
            MINIO_BUCKET,
            object_name,
            file.file,  # Pass the file stream directly
            length=-1,  # Let MinIO determine length from stream
            content_type=file.content_type or "application/octet-stream",
            part_size=10*1024*1024,  # 10MB chunks for multipart upload
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"message": "uploaded", "object_name": object_name}


@app.get("/download-file/{object_name}")
def download_file(object_name: str) -> StreamingResponse:
    try:
        response = client.get_object(MINIO_BUCKET, object_name)
        # Return streaming response for large files
        return StreamingResponse(
            response,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={object_name}"}
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/store-json")
def store_json(payload: JsonPayload) -> dict:
    object_name = payload.key
    data_bytes = json.dumps(payload.data, indent=2).encode("utf-8")
    try:
        client.put_object(
            MINIO_BUCKET,
            object_name,
            io.BytesIO(data_bytes),
            length=len(data_bytes),
            content_type="application/json",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"message": "json stored", "object_name": object_name}


@app.get("/retrieve-json/{object_name}")
def retrieve_json(object_name: str) -> JSONResponse:
    try:
        response = client.get_object(MINIO_BUCKET, object_name)
        raw = response.read()
        response.close()
        response.release_conn()
        payload = json.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return JSONResponse(content=payload)


@app.get("/file-info/{object_name}")
def get_file_info(object_name: str) -> dict:
    try:
        stat = client.stat_object(MINIO_BUCKET, object_name)
        return {
            "object_name": object_name,
            "size": stat.size,
            "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
            "content_type": stat.content_type,
            "etag": stat.etag,
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/list-objects")
def list_objects() -> dict:
    objects = [obj.object_name for obj in client.list_objects(MINIO_BUCKET)]
    return {"objects": objects}
