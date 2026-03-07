import pytest

pytestmark = pytest.mark.anyio


async def test_health_returns_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "clarity-backend"
    assert "thermal_enabled" in body


async def test_root_returns_api_info(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "Clarity+" in body["message"]
    assert body["docs"] == "/docs"
    assert body["health"] == "/health"
