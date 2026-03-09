"""Tests for the eye strain service (port 8005)."""

import pytest


@pytest.mark.asyncio
async def test_analyze_returns_score(eyes_client, temp_image_path):
    resp = await eyes_client.post("/analyze", json={"image_path": temp_image_path})
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "eyes"
    assert data["mode"] == "image"
    assert "score" in data
    assert "details" in data


@pytest.mark.asyncio
async def test_analyze_score_in_expected_range(eyes_client, temp_image_path):
    resp = await eyes_client.post("/analyze", json={"image_path": temp_image_path})
    score = resp.json()["score"]
    assert 0 <= score <= 100


@pytest.mark.asyncio
async def test_analyze_details_fields(eyes_client, temp_image_path):
    resp = await eyes_client.post("/analyze", json={"image_path": temp_image_path})
    details = resp.json()["details"]
    assert "blink_rate" in details
    assert "drowsiness" in details
    assert "ear" in details
    assert "eye_openness" in details
    assert "sclera_redness" in details
    assert "puffiness" in details


@pytest.mark.asyncio
async def test_analyze_image_not_found(eyes_client):
    resp = await eyes_client.post("/analyze", json={"image_path": "/nonexistent/photo.jpg"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "eyes"
    assert data["error"] == "image_not_found"
    assert data["score"] is None
