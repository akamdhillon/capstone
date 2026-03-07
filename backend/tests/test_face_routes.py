import json
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path

import pytest
import httpx

pytestmark = pytest.mark.anyio


def _mock_face_service_response(json_body: dict, status_code: int = 200):
    """Build a mock httpx.Response."""
    resp = httpx.Response(status_code, json=json_body, request=httpx.Request("POST", "http://fake"))
    return resp


@pytest.fixture(autouse=True)
def _patch_face_users_file(tmp_path):
    """Redirect the face-users JSON store to a temp directory."""
    tmp_file = tmp_path / "face_users.json"
    with patch("routes.face.FACE_USERS_FILE", tmp_file):
        yield tmp_file


# -- detect ----------------------------------------------------------------

async def test_detect_face_proxies_to_jetson(client):
    mock_resp = _mock_face_service_response({"face_detected": True, "bbox": [10, 20, 100, 120]})
    with patch("routes.face.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_resp
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        resp = await client.post("/api/face/detect", json={"image": "base64data"})
        assert resp.status_code == 200
        assert resp.json()["face_detected"] is True


# -- enroll -----------------------------------------------------------------

async def test_enroll_face_saves_to_file(client, _patch_face_users_file):
    jetson_resp = _mock_face_service_response({
        "embedding": [0.1] * 512,
        "quality_score": 0.95,
        "faces_processed": 3,
    })
    with patch("routes.face.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = jetson_resp
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        resp = await client.post("/api/face/enroll", json={"name": "Alice", "images": ["img1", "img2"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["name"] == "Alice"

        stored = json.loads(_patch_face_users_file.read_text())
        assert len(stored) == 1
        uid = list(stored.keys())[0]
        assert stored[uid]["name"] == "Alice"


# -- recognize --------------------------------------------------------------

async def test_recognize_face_returns_match(client, _patch_face_users_file):
    # Pre-seed a user
    users = {"uid-1": {"name": "Bob", "embedding": [0.1] * 512, "quality_score": 0.9}}
    _patch_face_users_file.write_text(json.dumps(users))

    jetson_resp = _mock_face_service_response({
        "match": True,
        "user_id": "uid-1",
        "confidence": 0.92,
        "match_type": "strong",
    })
    with patch("routes.face.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = jetson_resp
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        resp = await client.post("/api/face/recognize", json={"image": "base64data"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["match"] is True
        assert body["name"] == "Bob"


async def test_recognize_no_enrolled_users(client, _patch_face_users_file):
    resp = await client.post("/api/face/recognize", json={"image": "base64data"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["match"] is False
    assert body["match_type"] == "no_users"


# -- list users -------------------------------------------------------------

async def test_list_face_users_omits_embeddings(client, _patch_face_users_file):
    users = {
        "uid-1": {"name": "Bob", "embedding": [0.1] * 512, "quality_score": 0.9},
        "uid-2": {"name": "Carol", "embedding": [0.2] * 512, "quality_score": 0.88},
    }
    _patch_face_users_file.write_text(json.dumps(users))

    resp = await client.get("/api/face/users")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["users"]) == 2
    for u in body["users"]:
        assert "embedding" not in u
        assert "name" in u
