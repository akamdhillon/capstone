"""Tests for the thermal ghost service (port 8006)."""

import pytest


@pytest.mark.asyncio
async def test_analyze_returns_temperature(thermal_client):
    resp = await thermal_client.post("/analyze", json={"image_path": "/tmp/test.jpg"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "thermal"
    assert "temperature" in data
    assert "unit" in data


@pytest.mark.asyncio
async def test_temperature_in_expected_range(thermal_client):
    resp = await thermal_client.post("/analyze", json={"image_path": "/tmp/test.jpg"})
    temp = resp.json()["temperature"]
    assert 36.0 <= temp <= 37.0


@pytest.mark.asyncio
async def test_unit_is_celsius(thermal_client):
    resp = await thermal_client.post("/analyze", json={"image_path": "/tmp/test.jpg"})
    assert resp.json()["unit"] == "C"
