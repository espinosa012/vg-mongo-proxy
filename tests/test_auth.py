import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from vg_mongo_proxy.auth import verify_api_key


@pytest.fixture
def auth_app():
    test_app = FastAPI()

    @test_app.get("/protected")
    async def protected_route(key: str = Depends(verify_api_key)):
        return {"authorized": True}

    return test_app


@pytest.mark.asyncio
async def test_auth_missing_key(auth_app):
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as ac:
        response = await ac.get("/protected")
    assert response.status_code == 401
    assert "Invalid or missing API key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_auth_wrong_key(auth_app):
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as ac:
        response = await ac.get("/protected", headers={"x-api-key": "wrong-key"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_valid_key(auth_app):
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as ac:
        response = await ac.get("/protected", headers={"x-api-key": "dev-secret-key"})
    assert response.status_code == 200
    assert response.json()["authorized"] is True
