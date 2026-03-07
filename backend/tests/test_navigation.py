import pytest

pytestmark = pytest.mark.anyio


async def test_navigate_returns_correct_response(client):
    resp = await client.post("/api/navigate", json={"view": "posture"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["navigated_to"] == "posture"


async def test_action_returns_correct_response(client):
    resp = await client.post("/api/action", json={"action": "recognize"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["action"] == "recognize"


async def test_voice_status_returns_ok(client):
    resp = await client.post(
        "/api/voice/status",
        json={"state": "LISTENING", "user_id": "u1", "display_name": "Test"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
