import json
from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import pytest

pytestmark = pytest.mark.anyio


def _ollama_response(intent: str, message: str = "Sure.", actions=None):
    """Build a fake ollama.chat return value."""
    payload = {
        "assistant_message": message,
        "intent": intent,
        "actions": actions or [],
        "confidence": 0.95,
    }
    return {"message": {"content": json.dumps(payload)}}


def _fake_httpx_response(json_body=None, status_code=200):
    return httpx.Response(
        status_code,
        json=json_body or {"status": "ok"},
        request=httpx.Request("POST", "http://fake"),
    )


@pytest.fixture(autouse=True)
def _suppress_broadcasts():
    """Mock all outbound httpx calls made by voice_orchestrator (Jetson + self-calls)."""
    with patch("voice_orchestrator.httpx.AsyncClient") as MockCls:
        instance = AsyncMock()
        instance.post.return_value = _fake_httpx_response({"score": 80})
        instance.get.return_value = _fake_httpx_response({"total_assessments": 0})
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockCls.return_value = instance
        yield instance


async def test_posture_check_intent(client, mock_ollama):
    mock_ollama.return_value = _ollama_response("POSTURE_CHECK", "Ok, starting posture analysis.")
    resp = await client.post("/voice/intent", json={
        "user_text": "check my posture",
        "user_id": "u1",
        "display_name": "Test",
        "history": [],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "POSTURE_CHECK"
    assert "posture" in body["assistant_message"].lower()


async def test_navigate_home_intent(client, mock_ollama):
    mock_ollama.return_value = _ollama_response("NAVIGATE_HOME", "Going back to the mirror.")
    resp = await client.post("/voice/intent", json={
        "user_text": "go home",
        "user_id": "u1",
        "display_name": "Test",
        "history": [],
    })
    assert resp.status_code == 200
    assert resp.json()["intent"] == "NAVIGATE_HOME"


async def test_ollama_failure_returns_error_gracefully(client, mock_ollama):
    mock_ollama.side_effect = Exception("LLM unreachable")
    resp = await client.post("/voice/intent", json={
        "user_text": "hello",
        "user_id": "u1",
        "display_name": "Test",
        "history": [],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "ERROR"
    assert "sorry" in body["assistant_message"].lower() or "trouble" in body["assistant_message"].lower()


async def test_malformed_llm_json(client, mock_ollama):
    mock_ollama.return_value = {"message": {"content": "this is not json!!!"}}
    resp = await client.post("/voice/intent", json={
        "user_text": "check posture",
        "user_id": "u1",
        "display_name": "Test",
        "history": [],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "intent" in body
    assert "assistant_message" in body


async def test_jetson_action_execution(client, mock_ollama, _suppress_broadcasts):
    mock_ollama.return_value = _ollama_response(
        "POSTURE_CHECK",
        "Ok, starting posture analysis.",
        actions=[{"name": "run_posture_check", "params": {"user_id": "u1"}}],
    )
    resp = await client.post("/voice/intent", json={
        "user_text": "check posture",
        "user_id": "u1",
        "display_name": "Test",
        "history": [],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "POSTURE_CHECK"
    assert len(body["actions_run"]) == 1
    assert body["actions_run"][0]["name"] == "run_posture_check"


async def test_navigation_broadcast_for_posture(client, mock_ollama, _suppress_broadcasts):
    mock_ollama.return_value = _ollama_response("POSTURE_CHECK", "Ok, starting posture analysis.")
    resp = await client.post("/voice/intent", json={
        "user_text": "check posture",
        "user_id": "u1",
        "display_name": "Test",
        "history": [],
    })
    assert resp.status_code == 200
    calls = [str(c) for c in _suppress_broadcasts.post.call_args_list]
    nav_calls = [c for c in calls if "navigate" in c]
    assert len(nav_calls) > 0
