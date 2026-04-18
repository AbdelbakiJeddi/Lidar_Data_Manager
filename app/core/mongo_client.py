import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:rootpassword@mongodb:27017")
DB_NAME = os.getenv("DB_NAME", "lidar_db")

_client: AsyncIOMotorClient = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URI)
    return _client


def get_sync_mongo_client() -> MongoClient:
    return MongoClient(MONGO_URI)


async def get_database():
    client = get_mongo_client()
    return client[DB_NAME]


async def ensure_indexes(db):
    await db.datasets.create_index("status")
    await db.datasets.create_index("created_at")
    await db.datasets.create_index("object_name", unique=True)
    await db.octree_nodes.create_index([("dataset_id", 1), ("depth", 1)])
    await db.octree_nodes.create_index([("dataset_id", 1), ("node_id", 1)], unique=True)


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