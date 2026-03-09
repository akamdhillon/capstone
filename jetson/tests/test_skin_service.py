"""Tests for the skin analysis service (port 8003).

The skin service fails to start if the model is not loaded (no fallbacks).
Tests use a mock model (pytest mode) or require git lfs pull.
"""

from unittest.mock import patch, MagicMock
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_analyze_returns_acne_details(skin_client, tmp_path):
    """Skin analyze returns structured acne details when model (or mock) is loaded."""
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (64, 64), color="red")
    img_path = tmp_path / "test.jpg"
    img.save(img_path)
    resp = await skin_client.post("/analyze", json={"image_path": str(img_path)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "skin"
    assert "details" in data
    assert "acne" in data["details"]
    acne = data["details"]["acne"]
    assert "classification" in acne
    assert "severity_score" in acne
    assert "confidence" in acne


@pytest.mark.asyncio
async def test_analyze_with_model_success(tmp_path):
    """When the model is loaded, response should include real acne analysis."""
    import services.skin.main as skin_mod
    from PIL import Image as PILImage

    mock_inference = MagicMock()
    mock_inference.predict_single.return_value = {
        "class_idx": 1,
        "class_name": "Mild",
        "severity_score": 0.3,
        "confidence": 0.85,
    }

    img = PILImage.new("RGB", (64, 64), color="blue")
    img_path = tmp_path / "test.jpg"
    img.save(img_path)

    original_sys = skin_mod._inference_system
    skin_mod._inference_system = mock_inference
    try:
        transport = ASGITransport(app=skin_mod.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/analyze", json={"image_path": str(img_path)})
    finally:
        skin_mod._inference_system = original_sys

    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] is not None
    assert 0 <= data["score"] <= 100
    acne = data["details"]["acne"]
    assert acne["classification"] == "Mild"
    assert acne["severity_score"] == 3.0  # 0.3 * 10
    assert acne["confidence"] == 85.0  # 0.85 * 100
