import os
from minio import Minio
from minio.error import S3Error


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
