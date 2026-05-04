"""Centralized application settings.

This module provides typed settings loaded from environment variables and keeps
legacy module-level constants for compatibility with existing imports.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket_raw: str = "lidar-raw"
    minio_bucket_processed: str = "lidar-processed"

    mongo_uri: str = "mongodb://root:rootpassword@mongodb:27017"
    mongo_db_name: str = "lidar_db"

    pdal_bin: str = "pdal"


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()


# Backward-compatible constants.
_settings = get_settings()

BUCKET_RAW = _settings.minio_bucket_raw
BUCKET_PROCESSED = _settings.minio_bucket_processed
