import json

import pytest

pytestmark = pytest.mark.anyio

SAMPLE_POSTURE_RESULT = {
    "score": 75,
    "status": "moderate",
    "neck_angle": 5.2,
    "torso_angle": 3.1,
    "neck_status": "good",
    "torso_status": "good",
    "recommendations": [],
    "frames_analyzed": 300,
}


async def test_post_posture_result_saves_and_returns_count(client, tmp_posture_file):
    resp = await client.post("/api/posture/results", json=SAMPLE_POSTURE_RESULT)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["total_results"] == 1


async def test_get_posture_results_empty(client, tmp_posture_file):
    resp = await client.get("/api/posture/results")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_posture_results_returns_saved(client, tmp_posture_file):
    await client.post("/api/posture/results", json=SAMPLE_POSTURE_RESULT)
    resp = await client.get("/api/posture/results")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["score"] == 75


async def test_timestamp_auto_added(client, tmp_posture_file):
    await client.post("/api/posture/results", json=SAMPLE_POSTURE_RESULT)
    data = json.loads(tmp_posture_file.read_text())
    assert "timestamp" in data[0]


async def test_max_100_results_cap(client, tmp_posture_file):
    seed = [dict(SAMPLE_POSTURE_RESULT, timestamp="2026-01-01T00:00:00") for _ in range(99)]
    tmp_posture_file.write_text(json.dumps(seed))

    # Post two more to push total to 101, which should be capped at 100
    await client.post("/api/posture/results", json=SAMPLE_POSTURE_RESULT)
    await client.post("/api/posture/results", json=SAMPLE_POSTURE_RESULT)

    data = json.loads(tmp_posture_file.read_text())
    assert len(data) <= 100
