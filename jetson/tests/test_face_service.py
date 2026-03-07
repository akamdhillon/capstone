"""Tests for the face detection/enrollment/recognition service (port 8002)."""

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health(face_client):
    resp = await face_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "face"


# ---------------------------------------------------------------------------
# POST /face/detect
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_detect_with_face(face_client, fake_frame_b64):
    resp = await face_client.post("/face/detect", json={"image": fake_frame_b64})
    assert resp.status_code == 200
    data = resp.json()
    assert data["face_detected"] is True
    assert data["bbox"] is not None
    assert len(data["bbox"]) == 4
    assert data["landmarks"] is not None
    assert "latency_ms" in data


@pytest.mark.asyncio
async def test_detect_no_face(face_client_no_face, fake_frame_b64):
    resp = await face_client_no_face.post("/face/detect", json={"image": fake_frame_b64})
    assert resp.status_code == 200
    data = resp.json()
    assert data["face_detected"] is False
    assert data["bbox"] is None


# ---------------------------------------------------------------------------
# POST /face/enroll
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_enroll_success(face_client, fake_frame_b64):
    images = [fake_frame_b64] * 5
    resp = await face_client.post("/face/enroll", json={"images": images})
    assert resp.status_code == 200
    data = resp.json()
    assert "embedding" in data
    assert len(data["embedding"]) == 512
    assert 0 < data["quality_score"] <= 1.0
    assert data["faces_processed"] >= 1
    assert data["faces_submitted"] == 5


@pytest.mark.asyncio
async def test_enroll_too_few_images(face_client, fake_frame_b64):
    resp = await face_client.post("/face/enroll", json={"images": [fake_frame_b64]})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /face/recognize
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_recognize_known_user(face_client, fake_frame_b64, mock_insightface_face):
    known_emb = mock_insightface_face.normed_embedding.tolist()
    payload = {
        "image": fake_frame_b64,
        "known_embeddings": [
            {"user_id": "user-1", "embedding": known_emb}
        ],
    }
    resp = await face_client.post("/face/recognize", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # Same embedding → cosine similarity ~1.0 → strong match
    assert data["match"] is True
    assert data["user_id"] == "user-1"
    assert data["match_type"] == "strong"
    assert data["confidence"] >= 0.70


@pytest.mark.asyncio
async def test_recognize_unknown_user(face_client, fake_frame_b64):
    random_emb = np.random.randn(512).astype(np.float32)
    random_emb /= np.linalg.norm(random_emb)
    payload = {
        "image": fake_frame_b64,
        "known_embeddings": [
            {"user_id": "stranger", "embedding": random_emb.tolist()}
        ],
    }
    resp = await face_client.post("/face/recognize", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # Random embeddings in 512-d are nearly orthogonal → low similarity
    assert data["confidence"] < 0.70


@pytest.mark.asyncio
async def test_recognize_no_face(face_client_no_face, fake_frame_b64):
    payload = {
        "image": fake_frame_b64,
        "known_embeddings": [
            {"user_id": "user-1", "embedding": [0.0] * 512}
        ],
    }
    resp = await face_client_no_face.post("/face/recognize", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["match"] is False
    assert data["match_type"] == "no_face"


# ---------------------------------------------------------------------------
# POST /analyze  (orchestrator-facing legacy endpoint)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analyze_legacy_with_image(face_client, tmp_path, fake_frame):
    import cv2

    img_path = str(tmp_path / "test.jpg")
    cv2.imwrite(img_path, fake_frame)

    resp = await face_client.post("/analyze", json={"image_path": img_path})
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "face"
    assert data["faces_detected"] == 1


@pytest.mark.asyncio
async def test_analyze_legacy_missing_image(face_client):
    resp = await face_client.post("/analyze", json={"image_path": "/nonexistent/image.jpg"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "face"
    assert data["faces_detected"] == 0
