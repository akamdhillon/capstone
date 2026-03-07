"""Tests for the Jetson orchestrator (port 8001)."""

import base64
from unittest.mock import patch, MagicMock

import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _service_response(name, score=85):
    return {"service": name, "score": score, "details": {}}


SERVICE_PORTS = {"face": 8002, "skin": 8003, "posture": 8004, "eyes": 8005, "thermal": 8006}


def _mock_requests_post(url, json=None, timeout=None):
    resp = MagicMock()
    resp.status_code = 200
    for svc, port in SERVICE_PORTS.items():
        if f":{port}/" in url:
            resp.json.return_value = _service_response(svc)
            return resp
    resp.json.return_value = {"service": "unknown", "score": 0}
    return resp


def _mock_requests_post_partial(url, json=None, timeout=None):
    """face and skin succeed; posture/eyes/thermal raise."""
    for svc, port in [("face", 8002), ("skin", 8003)]:
        if f":{port}/" in url:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = _service_response(svc)
            return resp
    raise ConnectionError("Service unreachable")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def orch_client():
    import main as orch_mod

    mock_camera = MagicMock()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_camera.get_frame.return_value = frame
    mock_camera.start.return_value = True

    original_camera = orch_mod.camera
    orch_mod.camera = mock_camera
    try:
        with patch.object(orch_mod.requests, "post", side_effect=_mock_requests_post):
            transport = ASGITransport(app=orch_mod.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client
    finally:
        orch_mod.camera = original_camera


@pytest_asyncio.fixture
async def orch_client_partial():
    import main as orch_mod

    mock_camera = MagicMock()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_camera.get_frame.return_value = frame
    mock_camera.start.return_value = True

    original_camera = orch_mod.camera
    orch_mod.camera = mock_camera
    try:
        with patch.object(orch_mod.requests, "post", side_effect=_mock_requests_post_partial):
            transport = ASGITransport(app=orch_mod.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client
    finally:
        orch_mod.camera = original_camera


# ---------------------------------------------------------------------------
# POST /analyze — with base64 image
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analyze_with_image(orch_client, fake_frame_b64):
    resp = await orch_client.post("/analyze", json={"image": fake_frame_b64})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "timestamp" in data
    assert "results" in data
    assert "image" in data
    for svc in ("face", "skin", "posture", "eyes", "thermal"):
        assert svc in data["results"], f"Missing result for {svc}"


# ---------------------------------------------------------------------------
# POST /analyze — no image (camera capture)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analyze_camera_capture(orch_client):
    resp = await orch_client.post("/analyze", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "results" in data


# ---------------------------------------------------------------------------
# Individual service failures don't crash orchestrator
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analyze_partial_failure(orch_client_partial, fake_frame_b64):
    resp = await orch_client_partial.post("/analyze", json={"image": fake_frame_b64})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "face" in data["results"]
    assert "skin" in data["results"]
    for svc in ("posture", "eyes", "thermal"):
        assert svc in data["results"]
        assert "error" in data["results"][svc]


# ---------------------------------------------------------------------------
# Response includes base64 image
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_response_includes_image(orch_client, fake_frame_b64):
    resp = await orch_client.post("/analyze", json={"image": fake_frame_b64})
    data = resp.json()
    assert data["image"] is not None
    decoded = base64.b64decode(data["image"])
    assert len(decoded) > 0
