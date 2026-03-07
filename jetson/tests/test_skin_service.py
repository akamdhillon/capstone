"""Tests for the skin analysis service (port 8003)."""

from unittest.mock import patch, MagicMock
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_analyze_fallback_returns_acne_key(skin_client):
    """When the model is unavailable, fallback response should still use 'acne' key."""
    resp = await skin_client.post("/analyze", json={"image_path": "/tmp/test.jpg"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "skin"
    assert "acne" in data["details"], "Fallback should use 'acne' key, not 'texture'/'hydration'"


@pytest.mark.asyncio
async def test_analyze_fallback_score_range(skin_client):
    resp = await skin_client.post("/analyze", json={"image_path": "/tmp/test.jpg"})
    score = resp.json()["score"]
    assert 0 <= score <= 100


@pytest.mark.asyncio
async def test_analyze_fallback_acne_shape(skin_client):
    """Fallback acne details should have the same fields as the model response."""
    resp = await skin_client.post("/analyze", json={"image_path": "/tmp/test.jpg"})
    acne = resp.json()["details"]["acne"]
    assert "classification" in acne
    assert "severity_score" in acne
    assert "confidence" in acne
    assert "score" in acne


@pytest.mark.asyncio
async def test_analyze_fallback_confidence_is_zero(skin_client):
    """Fallback should report zero confidence since no real model ran."""
    resp = await skin_client.post("/analyze", json={"image_path": "/tmp/test.jpg"})
    acne = resp.json()["details"]["acne"]
    assert acne["confidence"] == 0.0


@pytest.mark.asyncio
async def test_analyze_with_model_success():
    """When the model is loaded, response should include real acne analysis."""
    import services.skin.main as skin_mod

    mock_inference = MagicMock()
    mock_inference.predict_single.return_value = {
        "class_name": "Mild",
        "severity_score": 0.3,
        "confidence": 0.85,
    }

    mock_image = MagicMock()
    mock_image_class = MagicMock()
    mock_image_class.open.return_value.convert.return_value = mock_image

    original_sys = skin_mod._inference_system
    skin_mod._inference_system = mock_inference
    try:
        with patch("PIL.Image", mock_image_class):
            transport = ASGITransport(app=skin_mod.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/analyze", json={"image_path": "/tmp/test.jpg"})
    finally:
        skin_mod._inference_system = original_sys

    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 70  # (1 - 0.3) * 100
    acne = data["details"]["acne"]
    assert acne["classification"] == "Mild"
    assert acne["severity_score"] == 3.0  # 0.3 * 10
    assert acne["confidence"] == 85.0  # 0.85 * 100
