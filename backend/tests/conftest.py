import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from httpx import ASGITransport, AsyncClient as _RealAsyncClient

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app, POSTURE_RESULTS_FILE
import main as main_module

# Hold a direct reference so patches on httpx.AsyncClient don't break our test client.
_saved_async_client = _RealAsyncClient


@pytest.fixture()
def anyio_backend():
    return "asyncio"


@pytest.fixture()
async def client():
    """Async HTTP client wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with _saved_async_client(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture()
def tmp_posture_file(tmp_path):
    """Redirect POSTURE_RESULTS_FILE to a temp location for the duration of the test."""
    tmp_file = tmp_path / "posture_results.json"
    original = main_module.POSTURE_RESULTS_FILE
    main_module.POSTURE_RESULTS_FILE = tmp_file
    yield tmp_file
    main_module.POSTURE_RESULTS_FILE = original


@pytest.fixture()
def tmp_face_users_file(tmp_path):
    """Provide a temporary face_users.json for face route tests."""
    tmp_file = tmp_path / "face_users.json"
    return tmp_file


@pytest.fixture()
def mock_ollama():
    """Patch ollama.chat so no real LLM call is made."""
    with patch("voice_orchestrator.ollama.chat") as mocked:
        yield mocked


@pytest.fixture()
def mock_jetson_httpx():
    """Patch httpx.AsyncClient used inside voice_orchestrator for Jetson calls."""
    with patch("voice_orchestrator.httpx.AsyncClient") as mocked:
        yield mocked


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
