import json

import pytest

pytestmark = pytest.mark.anyio


async def test_summary_no_data(client, tmp_posture_file):
    resp = await client.get("/api/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_assessments"] == 0
    assert body["trend"] == "no_data"


async def test_summary_with_data(client, tmp_posture_file):
    entries = [
        {"score": 40, "status": "poor", "timestamp": "2026-03-01T10:00:00"},
        {"score": 60, "status": "moderate", "timestamp": "2026-03-02T10:00:00"},
        {"score": 80, "status": "good", "timestamp": "2026-03-03T10:00:00"},
    ]
    tmp_posture_file.write_text(json.dumps(entries))

    resp = await client.get("/api/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_assessments"] == 3
    assert body["average_score"] == 60.0
    assert body["trend"] == "improving"
    assert body["latest"]["score"] == 80


async def test_summary_declining_trend(client, tmp_posture_file):
    entries = [
        {"score": 90, "status": "good", "timestamp": "2026-03-01T10:00:00"},
        {"score": 50, "status": "poor", "timestamp": "2026-03-02T10:00:00"},
    ]
    tmp_posture_file.write_text(json.dumps(entries))

    resp = await client.get("/api/summary")
    body = resp.json()
    assert body["trend"] == "declining"
