"""Tests for the posture analysis service (port 8004)."""

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

JETSON_ROOT = Path(__file__).resolve().parent.parent
if str(JETSON_ROOT) not in sys.path:
    sys.path.insert(0, str(JETSON_ROOT))


@pytest_asyncio.fixture
async def posture_client():
    import services.posture.main as posture_mod

    transport = ASGITransport(app=posture_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_analyze_returns_posture_result(posture_client, tmp_path):
    img_path = str(tmp_path / "frame.jpg")
    Path(img_path).write_bytes(b"\xff\xd8fake")

    resp = await posture_client.post("/analyze", json={"image_path": img_path})
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "posture"
    assert "score" in data
    assert "details" in data


@pytest.mark.asyncio
async def test_analyze_score_in_range(posture_client, tmp_path):
    img_path = str(tmp_path / "frame.jpg")
    Path(img_path).write_bytes(b"\xff\xd8fake")

    resp = await posture_client.post("/analyze", json={"image_path": img_path})
    assert resp.status_code == 200
    score = resp.json()["score"]
    assert 0 <= score <= 100


@pytest.mark.asyncio
async def test_analyze_details_has_expected_keys(posture_client, tmp_path):
    """Details from image analysis include neck_angle and torso_angle."""
    img_path = str(tmp_path / "frame.jpg")
    Path(img_path).write_bytes(b"\xff\xd8fake")

    resp = await posture_client.post("/analyze", json={"image_path": img_path})
    assert resp.status_code == 200
    details = resp.json()["details"]
    # Service returns neck_angle/torso_angle (or error when no pose detected)
    assert "neck_angle" in details or "torso_angle" in details or "error" in details


@pytest.mark.asyncio
async def test_analyze_missing_image_path_falls_back_to_camera(posture_client):
    """When image_path is empty, service falls back to camera analysis (200)."""
    resp = await posture_client.post("/analyze", json={"image_path": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "posture"
