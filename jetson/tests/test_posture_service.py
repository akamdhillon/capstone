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
    img_path = str(tmp_path / "frame.jpg")
    Path(img_path).write_bytes(b"\xff\xd8fake")

    resp = await posture_client.post("/analyze", json={"image_path": img_path})
    assert resp.status_code == 200
    details = resp.json()["details"]
    assert "head_tilt" in details
    assert "shoulder_alignment" in details


@pytest.mark.asyncio
async def test_analyze_missing_image_path_returns_422(posture_client):
    resp = await posture_client.post("/analyze", json={})
    assert resp.status_code == 422
