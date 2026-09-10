import pytest
from httpx import AsyncClient, ASGITransport
from urja_api.main import app

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "cache" in data

@pytest.mark.asyncio
async def test_list_meters():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/meters?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "meters" in data
        assert "total" in data
        assert "page" in data

@pytest.mark.asyncio
async def test_transformers_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/transformers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "code" in data[0]
            assert "capacity_kva" in data[0]

@pytest.mark.asyncio
async def test_hierarchy_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/hierarchy")
        assert resp.status_code == 200
        data = resp.json()
        assert "tree" in data
        assert "total_zones" in data

@pytest.mark.asyncio
async def test_nearby_meters():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/meters/nearby?lat=26.9124&lng=75.7873&radius_km=10")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

@pytest.mark.asyncio
async def test_not_found_meter():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/meters/NONEXISTENT_METER_ID_99999")
        assert resp.status_code == 404
