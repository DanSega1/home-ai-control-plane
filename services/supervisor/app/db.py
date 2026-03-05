"""MongoDB async client (motor)."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def init_mongo() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongo_uri)
    _db = _client[settings.mongo_db]
    # Create indexes on first run
    await _db["tasks"].create_index("task_id", unique=True)
    await _db["tasks"].create_index("status")
    await _db["model_usage"].create_index("timestamp")
    await _db["model_usage"].create_index("task_id")


async def close_mongo() -> None:
    if _client:
        _client.close()


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB not initialised - call init_mongo() first.")
    return _db
