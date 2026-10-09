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

        resp_v1 = await ac.get("/api/v1/health")
        assert resp_v1.status_code == 200

@pytest.mark.asyncio
async def test_auth_login_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/auth/login", json={
            "username": "operator@urja.local",
            "password": "urja-ops-2026"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["authenticated"] is True
        assert data["session_token_present"] is True

@pytest.mark.asyncio
async def test_list_meters():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test v1 endpoint
        resp = await ac.get("/api/v1/meters?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "meters" in data
        assert "total" in data
        assert "page" in data

        # Test unversioned alias
        resp_alias = await ac.get("/api/meters?page=1&page_size=10")
        assert resp_alias.status_code == 200

@pytest.mark.asyncio
async def test_meter_detail_and_consumption():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # List first to get a valid meter
        list_resp = await ac.get("/api/v1/meters?page=1&page_size=1")
        assert list_resp.status_code == 200
        meters = list_resp.json()["meters"]
        if meters:
            meter_id = meters[0]["meter_id"]
            # Test v1 meter detail
            detail_resp = await ac.get(f"/api/v1/meters/{meter_id}")
            assert detail_resp.status_code == 200
            detail = detail_resp.json()
            assert detail["meter_id"] == meter_id
            assert "nameplate" in detail

            # Test v1 consumption
            cons_resp = await ac.get(f"/api/v1/meters/{meter_id}/consumption")
            assert cons_resp.status_code == 200
            cons = cons_resp.json()
            assert cons["meter_id"] == meter_id
            assert "total_readings" in cons

@pytest.mark.asyncio
async def test_transformers_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/transformers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "code" in data[0]
            assert "capacity_kva" in data[0]

@pytest.mark.asyncio
async def test_hierarchy_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/hierarchy")
        assert resp.status_code == 200
        data = resp.json()
        assert "tree" in data
        assert "total_zones" in data

@pytest.mark.asyncio
async def test_nearby_meters():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/meters/nearby?lat=26.9124&lng=75.7873&radius_km=10")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

@pytest.mark.asyncio
async def test_not_found_meter():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/meters/NONEXISTENT_METER_ID_99999")
        assert resp.status_code == 404
