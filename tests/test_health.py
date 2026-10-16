from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from vg_mongo_proxy.main import create_app


@pytest.mark.asyncio
async def test_root_endpoint():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "vg-mongo-proxy"
    assert data["status"] == "online"


@pytest.mark.asyncio
async def test_health_healthy():
    app = create_app()
    with patch("vg_mongo_proxy.main.ping_database", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = {"connected": True, "latency_ms": 12.5}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["latency_ms"] == 12.5


@pytest.mark.asyncio
async def test_health_unhealthy():
    app = create_app()
    with patch("vg_mongo_proxy.main.ping_database", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = {"connected": False, "error": "Connection refused"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
