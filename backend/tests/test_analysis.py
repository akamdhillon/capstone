from unittest.mock import patch, AsyncMock

import pytest
import httpx

pytestmark = pytest.mark.anyio


def _jetson_analyze_response():
    """Simulated Jetson /analyze response."""
    return {
        "success": True,
        "results": {
            "skin": {"score": 80},
            "posture": {"score": 70},
            "eyes": {"score": 90},
            "thermal": {"score": 60},
        },
        "image": "base64img",
        "errors": [],
    }


def _mock_httpx_response(json_body, status_code=200):
    return httpx.Response(status_code, json=json_body, request=httpx.Request("POST", "http://fake"))


@pytest.fixture(autouse=True)
def _mock_jetson(monkeypatch):
    """Patch JetsonClient._make_request so no real Jetson calls are made."""
    async def fake_make_request(self, endpoint, method="POST", data=None):
        if endpoint == "/analyze":
            return _jetson_analyze_response(), None
        if endpoint == "/health":
            return {"status": "ok"}, None
        return None, "Not found"

    monkeypatch.setattr("services.jetson_client.JetsonClient._make_request", fake_make_request)


async def test_analyze_returns_scored_results(client):
    resp = await client.post("/api/analyze", json={"user_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert "overall_score" in body
    assert body["scores"]["skin"] == 80


async def test_jetson_health(client):
    resp = await client.get("/api/jetson/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "thermal_enabled" in body


async def test_debug_analyze(client):
    resp = await client.post("/api/debug/analyze", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "overall_score" in body


async def test_debug_analyze_with_image(client):
    resp = await client.post("/api/debug/analyze", json={"image": "base64data"})
    assert resp.status_code == 200
    assert resp.json()["success"] is True
