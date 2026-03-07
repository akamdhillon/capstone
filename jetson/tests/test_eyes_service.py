"""Tests for the eye strain placeholder service (port 8005)."""

import pytest


@pytest.mark.asyncio
async def test_analyze_returns_score(eyes_client):
    resp = await eyes_client.post("/analyze", json={"image_path": "/tmp/test.jpg"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "eyes"
    assert "score" in data
    assert "details" in data


@pytest.mark.asyncio
async def test_analyze_score_in_expected_range(eyes_client):
    resp = await eyes_client.post("/analyze", json={"image_path": "/tmp/test.jpg"})
    score = resp.json()["score"]
    assert 80 <= score <= 100


@pytest.mark.asyncio
async def test_analyze_details_fields(eyes_client):
    resp = await eyes_client.post("/analyze", json={"image_path": "/tmp/test.jpg"})
    details = resp.json()["details"]
    assert "blink_rate" in details
    assert "drowsiness" in details
