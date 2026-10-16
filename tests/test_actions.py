from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
import pytest
from httpx import ASGITransport, AsyncClient

from vg_mongo_proxy.main import create_app

AUTH_HEADERS = {"x-api-key": "dev-secret-key"}


@pytest.fixture
def mock_db_collection():
    with patch("vg_mongo_proxy.routes.actions.get_database") as mock_get_db:
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        mock_get_db.return_value = mock_db
        yield mock_col


@pytest.mark.asyncio
async def test_find(mock_db_collection):
    fake_docs = [
        {"_id": ObjectId("60d5ec49f1b2c8b1f8e4e1a1"), "title": "Task 1", "status": "pending"},
        {"_id": ObjectId("60d5ec49f1b2c8b1f8e4e1a2"), "title": "Task 2", "status": "done"},
    ]
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=fake_docs)
    mock_db_collection.find.return_value = cursor

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/action/find",
            headers=AUTH_HEADERS,
            json={"collection": "tasks", "filter": {"status": "pending"}},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["documents"]) == 2
    assert data["documents"][0]["_id"] == "60d5ec49f1b2c8b1f8e4e1a1"
    assert data["documents"][0]["title"] == "Task 1"


@pytest.mark.asyncio
async def test_find_one(mock_db_collection):
    fake_doc = {"_id": ObjectId("60d5ec49f1b2c8b1f8e4e1a1"), "title": "Solo task"}
    mock_db_collection.find_one = AsyncMock(return_value=fake_doc)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/action/findOne",
            headers=AUTH_HEADERS,
            json={"collection": "tasks", "filter": {"_id": "60d5ec49f1b2c8b1f8e4e1a1"}},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["document"]["_id"] == "60d5ec49f1b2c8b1f8e4e1a1"
    assert data["document"]["title"] == "Solo task"


@pytest.mark.asyncio
async def test_count(mock_db_collection):
    mock_db_collection.count_documents = AsyncMock(return_value=42)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/action/count",
            headers=AUTH_HEADERS,
            json={"collection": "tasks", "filter": {}},
        )

    assert resp.status_code == 200
    assert resp.json()["count"] == 42


@pytest.mark.asyncio
async def test_insert_one(mock_db_collection):
    res = MagicMock()
    res.inserted_id = ObjectId("60d5ec49f1b2c8b1f8e4e1a1")
    mock_db_collection.insert_one = AsyncMock(return_value=res)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/action/insertOne",
            headers=AUTH_HEADERS,
            json={"collection": "tasks", "document": {"title": "New Task"}},
        )

    assert resp.status_code == 201
    assert resp.json()["insertedId"] == "60d5ec49f1b2c8b1f8e4e1a1"


@pytest.mark.asyncio
async def test_insert_many(mock_db_collection):
    res = MagicMock()
    res.inserted_ids = [ObjectId("60d5ec49f1b2c8b1f8e4e1a1"), ObjectId("60d5ec49f1b2c8b1f8e4e1a2")]
    mock_db_collection.insert_many = AsyncMock(return_value=res)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/action/insertMany",
            headers=AUTH_HEADERS,
            json={"collection": "tasks", "documents": [{"title": "T1"}, {"title": "T2"}]},
        )

    assert resp.status_code == 201
    assert len(resp.json()["insertedIds"]) == 2


@pytest.mark.asyncio
async def test_update_one(mock_db_collection):
    res = MagicMock()
    res.matched_count = 1
    res.modified_count = 1
    res.upserted_id = None
    mock_db_collection.update_one = AsyncMock(return_value=res)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/action/updateOne",
            headers=AUTH_HEADERS,
            json={
                "collection": "tasks",
                "filter": {"_id": "60d5ec49f1b2c8b1f8e4e1a1"},
                "update": {"$set": {"status": "completed"}},
            },
        )

    assert resp.status_code == 200
    assert resp.json()["matchedCount"] == 1
    assert resp.json()["modifiedCount"] == 1


@pytest.mark.asyncio
async def test_delete_one(mock_db_collection):
    res = MagicMock()
    res.deleted_count = 1
    mock_db_collection.delete_one = AsyncMock(return_value=res)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/action/deleteOne",
            headers=AUTH_HEADERS,
            json={"collection": "tasks", "filter": {"_id": "60d5ec49f1b2c8b1f8e4e1a1"}},
        )

    assert resp.status_code == 200
    assert resp.json()["deletedCount"] == 1


@pytest.mark.asyncio
async def test_aggregate(mock_db_collection):
    fake_results = [{"_id": "pending", "count": 5}, {"_id": "done", "count": 12}]
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=fake_results)
    mock_db_collection.aggregate.return_value = cursor

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/action/aggregate",
            headers=AUTH_HEADERS,
            json={
                "collection": "tasks",
                "pipeline": [{"$group": {"_id": "$status", "count": {"$sum": 1}}}],
            },
        )

    assert resp.status_code == 200
    assert len(resp.json()["documents"]) == 2
