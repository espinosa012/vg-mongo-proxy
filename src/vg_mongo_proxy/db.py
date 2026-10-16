from __future__ import annotations

import time
from typing import Dict, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket

from vg_mongo_proxy.config import get_settings

# Active primary client
_client: Optional[AsyncIOMotorClient] = None

# Cache for dynamic URI connections
_client_cache: Dict[str, AsyncIOMotorClient] = {}


async def init_db(uri: Optional[str] = None) -> AsyncIOMotorClient:
    """Initialize primary MongoDB client."""
    global _client
    settings = get_settings()
    connection_uri = uri or settings.mongodb_uri

    _client = AsyncIOMotorClient(
        connection_uri,
        serverSelectionTimeoutMS=5000,
        maxPoolSize=50,
        minPoolSize=5,
    )
    return _client


async def close_db() -> None:
    """Close primary and cached MongoDB connections."""
    global _client, _client_cache
    if _client is not None:
        _client.close()
        _client = None

    for cached_client in _client_cache.values():
        cached_client.close()
    _client_cache.clear()


def get_client(custom_uri: Optional[str] = None) -> AsyncIOMotorClient:
    """Get active MongoDB client, creating a cached one if a custom URI is provided."""
    global _client, _client_cache

    if custom_uri:
        if custom_uri not in _client_cache:
            _client_cache[custom_uri] = AsyncIOMotorClient(
                custom_uri,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=20,
            )
        return _client_cache[custom_uri]

    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=50,
            minPoolSize=5,
        )
    return _client


def get_database(
    database_name: Optional[str] = None,
    custom_uri: Optional[str] = None,
) -> AsyncIOMotorDatabase:
    """Return database instance for given name or default configured database."""
    settings = get_settings()
    client = get_client(custom_uri)
    db_name = database_name or settings.default_database
    return client[db_name]


def get_gridfs_bucket(
    database_name: Optional[str] = None,
    custom_uri: Optional[str] = None,
    bucket_name: str = "fs",
) -> AsyncIOMotorGridFSBucket:
    """Return GridFS bucket instance."""
    db = get_database(database_name, custom_uri)
    return AsyncIOMotorGridFSBucket(db, bucket_name=bucket_name)


async def ping_database(custom_uri: Optional[str] = None) -> dict:
    """Ping MongoDB server and calculate round-trip latency in milliseconds."""
    client = get_client(custom_uri)
    start = time.perf_counter()
    try:
        await client.admin.command("ping")
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"connected": True, "latency_ms": elapsed_ms}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}
