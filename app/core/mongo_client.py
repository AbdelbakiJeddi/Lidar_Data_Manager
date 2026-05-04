import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from pymongo.errors import OperationFailure, DuplicateKeyError
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
    logger = logging.getLogger(__name__)
    await db.datasets.create_index("status")
    await db.datasets.create_index("created_at")
    await db.datasets.create_index("object_name", unique=True)

    # Drop stale indexes from previous schema versions (grid_index -> grid_x/grid_y)
    stale_indexes = ["dataset_id_1_grid_index_1"]
    for idx_name in stale_indexes:
        try:
            await db.tiles.drop_index(idx_name)
            logger.info(f"Dropped stale index: {idx_name}")
        except OperationFailure:
            pass  # Index doesn't exist, nothing to drop

    try:
        await db.tiles.create_index(
            [("dataset_id", 1), ("grid_x", 1), ("grid_y", 1)],
            unique=True,
            name="dataset_id_1_grid_x_1_grid_y_1",
        )
    except Exception as exc:
        # If there's an index specs conflict or duplicate key, drop the collection and recreate index
        logger.warning("Error creating index dataset_id_1_grid_x_1_grid_y_1. Dropping conflicting tiles collection.")
        await db.tiles.drop()
        await db.tiles.create_index(
            [("dataset_id", 1), ("grid_x", 1), ("grid_y", 1)],
            unique=True,
            name="dataset_id_1_grid_x_1_grid_y_1",
        )
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