import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from gridfs.errors import NoFile
import pytest
from httpx import ASGITransport, AsyncClient

from vg_mongo_proxy.main import create_app

AUTH_HEADERS = {"x-api-key": "dev-secret-key"}


@pytest.fixture
def mock_gridfs():
    with patch("vg_mongo_proxy.routes.files.get_gridfs_bucket") as mock_get_bucket:
        mock_bucket = MagicMock()
        mock_get_bucket.return_value = mock_bucket
        yield mock_bucket


@pytest.mark.asyncio
async def test_upload_file(mock_gridfs):
    fake_id = ObjectId("60d5ec49f1b2c8b1f8e4e1a1")
    upload_stream = MagicMock()
    upload_stream._id = fake_id
    upload_stream.length = 13
    upload_stream.write = AsyncMock()
    upload_stream.close = AsyncMock()
    mock_gridfs.open_upload_stream.return_value = upload_stream

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("test.txt", b"Hello, World!", "text/plain")}
        resp = await ac.post("/files/upload", headers=AUTH_HEADERS, files=files)

    assert resp.status_code == 201
    data = resp.json()
    assert data["fileId"] == "60d5ec49f1b2c8b1f8e4e1a1"
    assert data["filename"] == "test.txt"
    assert data["contentType"] == "text/plain"
    assert data["length"] == 13


@pytest.mark.asyncio
async def test_download_file(mock_gridfs):
    fake_id = ObjectId("60d5ec49f1b2c8b1f8e4e1a1")
    grid_out = MagicMock()
    grid_out._id = fake_id
    grid_out.filename = "test.txt"
    grid_out.length = 13
    grid_out.metadata = {"contentType": "text/plain"}

    # Mock chunk reading
    chunks = [b"Hello, ", b"World!", b""]
    grid_out.readchunk = AsyncMock(side_effect=chunks)
    mock_gridfs.open_download_stream = AsyncMock(return_value=grid_out)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/files/{fake_id}", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert resp.content == b"Hello, World!"
    assert "text/plain" in resp.headers["content-type"]
    assert "test.txt" in resp.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_file_via_query_key(mock_gridfs):
    fake_id = ObjectId("60d5ec49f1b2c8b1f8e4e1a1")
    grid_out = MagicMock()
    grid_out.filename = "photo.png"
    grid_out.length = 4
    grid_out.metadata = {"contentType": "image/png"}
    grid_out.readchunk = AsyncMock(side_effect=[b"\x89PNG", b""])
    mock_gridfs.open_download_stream = AsyncMock(return_value=grid_out)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/files/{fake_id}?key=dev-secret-key")

    assert resp.status_code == 200
    assert resp.content == b"\x89PNG"
    assert resp.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_get_file_info(mock_gridfs):
    fake_id = ObjectId("60d5ec49f1b2c8b1f8e4e1a1")
    now = datetime.datetime.now(datetime.timezone.utc)
    grid_out = MagicMock()
    grid_out._id = fake_id
    grid_out.filename = "test.txt"
    grid_out.length = 100
    grid_out.upload_date = now
    grid_out.metadata = {"contentType": "text/plain"}
    mock_gridfs.open_download_stream = AsyncMock(return_value=grid_out)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/files/{fake_id}/info", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["fileId"] == str(fake_id)
    assert data["length"] == 100
    assert data["filename"] == "test.txt"


@pytest.mark.asyncio
async def test_delete_file(mock_gridfs):
    fake_id = ObjectId("60d5ec49f1b2c8b1f8e4e1a1")
    mock_gridfs.delete = AsyncMock()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete(f"/files/{fake_id}", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_file_not_found(mock_gridfs):
    fake_id = ObjectId("60d5ec49f1b2c8b1f8e4e1a1")
    mock_gridfs.open_download_stream = AsyncMock(side_effect=NoFile)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/files/{fake_id}", headers=AUTH_HEADERS)

    assert resp.status_code == 404
