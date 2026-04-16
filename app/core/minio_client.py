import os
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

BUCKET_RAW = "lidar-raw"
BUCKET_PROCESSED = "lidar-processed"


def get_minio_client() -> Minio:
    endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    secure = os.getenv("MINIO_SECURE", "false").lower() in ("1", "true", "yes")

    return Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
    )


def ensure_bucket(client: Minio, bucket_name: str) -> None:
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        logger.info(f"Created bucket: {bucket_name}")


def ensure_buckets(client: Minio = None) -> None:
    if client is None:
        client = get_minio_client()
    ensure_bucket(client, BUCKET_RAW)
    ensure_bucket(client, BUCKET_PROCESSED)


def upload_local_file(
    client: Minio,
    bucket_name: str,
    local_path: str,
    object_name: str,
    content_type: str = "application/octet-stream",
    metadata: Dict[str, str] = None
) -> None:
    client.fput_object(
        bucket_name,
        object_name,
        local_path,
        content_type=content_type,
        metadata=metadata or {},
    )
    logger.debug(f"Uploaded {local_path} to {bucket_name}/{object_name}")


def download_file(
    client: Minio,
    bucket_name: str,
    object_name: str,
    local_path: str
) -> None:
    client.fget_object(bucket_name, object_name, local_path)
    logger.debug(f"Downloaded {bucket_name}/{object_name} to {local_path}")


def get_object_url(client: Minio, bucket_name: str, object_name: str) -> str:
    endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
    return f"http://{endpoint}/{bucket_name}/{object_name}"


def list_objects(client: Minio, bucket_name: str, prefix: str = "") -> list:
    return list(client.list_objects(bucket_name, prefix=prefix))


def delete_object(client: Minio, bucket_name: str, object_name: str) -> None:
    client.remove_object(bucket_name, object_name)
    logger.debug(f"Deleted {bucket_name}/{object_name}")


def check_minio_health(client: Minio = None) -> Dict[str, Any]:
    if client is None:
        client = get_minio_client()
    try:
        buckets = client.list_buckets()
        return {"status": "healthy", "buckets": [b.name for b in buckets]}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
