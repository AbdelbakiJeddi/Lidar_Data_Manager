import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from app.core.settings import get_settings

_settings = get_settings()
MONGO_URI = _settings.mongo_uri
DB_NAME = _settings.mongo_db_name

_client: AsyncIOMotorClient = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URI)
    return _client


def get_sync_mongo_client() -> MongoClient:
    return MongoClient(MONGO_URI)


def close_mongo_client() -> None:
    """Close async Mongo client if it was initialized."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def get_database():
    client = get_mongo_client()
    return client[DB_NAME]


async def ensure_indexes(db):
    await db.datasets.create_index("status")
    await db.datasets.create_index("created_at")
    await db.datasets.create_index("object_name", unique=True)
    await db.tiles.create_index([("dataset_id", 1), ("grid_index", 1)])
    await db.tiles.create_index([("dataset_id", 1), ("bbox.min_x", 1), ("bbox.min_y", 1)])


async def check_mongo_health() -> dict:
    """Check MongoDB connection health."""
    try:
        client = get_mongo_client()
        await client.admin.command("ping")
        return {"status": "healthy", "uri": MONGO_URI}
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"MongoDB health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}