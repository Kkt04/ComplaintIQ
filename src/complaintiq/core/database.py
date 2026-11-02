from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from complaintiq.core.config import settings
from complaintiq.core.logging import logger

_mongo_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None
_is_mock: bool = False


async def get_db_client() -> AsyncIOMotorClient:
    global _mongo_client, _is_mock
    if _mongo_client is None:
        try:
            # Attempt connection to real MongoDB with 1.5s server selection timeout
            client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                serverSelectionTimeoutMS=1500,
            )
            # Ping to verify reachability
            await client.admin.command("ping")
            _mongo_client = client
            _is_mock = False
            logger.info(f"Connected to MongoDB at {settings.MONGODB_URL}")
        except Exception as e:
            if settings.USE_MOCK_DB_IF_UNAVAILABLE:
                logger.warning(f"Could not connect to live MongoDB ({e}). Falling back to in-memory mongomock-motor datastore.")
                from mongomock_motor import AsyncMongoMockClient
                _mongo_client = AsyncMongoMockClient()
                _is_mock = True
            else:
                raise
    return _mongo_client


async def get_database() -> AsyncIOMotorDatabase:
    global _database
    if _database is None:
        client = await get_db_client()
        _database = client[settings.DATABASE_NAME]
    return _database


def is_mock_database() -> bool:
    return _is_mock


async def close_db_connection() -> None:
    global _mongo_client, _database
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        _database = None
        logger.info("MongoDB connection closed.")
