"""
Shared fixtures for Jetson ML service tests.

All external dependencies (camera, InsightFace, PyTorch, MediaPipe) are mocked
at the sys.modules level so tests run on any machine without hardware or heavy
model weights.
"""

import sys
import os
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

JETSON_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Inject mock modules for heavy ML libraries that may not be installed
# ---------------------------------------------------------------------------

def _ensure_mock_module(name, attrs=None):
    """Register a mock module in sys.modules if the real one isn't available."""
    if name not in sys.modules:
        mod = types.ModuleType(name)
        if attrs:
            for k, v in attrs.items():
                setattr(mod, k, v)
        sys.modules[name] = mod
    return sys.modules[name]


def _setup_insightface_mocks():
    _ensure_mock_module("insightface")
    _ensure_mock_module("insightface.app", {"FaceAnalysis": MagicMock})


def _setup_mediapipe_mocks():
    mp_mod = _ensure_mock_module("mediapipe")

    # Build a fake PoseLandmark enum
    class FakePoseLandmark:
        LEFT_SHOULDER = 11
        RIGHT_SHOULDER = 12
        LEFT_EAR = 7
        LEFT_HIP = 23

    pose_mod = MagicMock()
    pose_mod.PoseLandmark = FakePoseLandmark
    pose_mod.Pose = MagicMock

    solutions_mod = _ensure_mock_module("mediapipe.solutions", {"pose": pose_mod})
    solutions_mod.pose = pose_mod

    mp_mod.solutions = solutions_mod


def _setup_torch_mocks():
    if "torch" not in sys.modules:
        _ensure_mock_module("torch")
        _ensure_mock_module("torchvision")
        _ensure_mock_module("torchvision.transforms")
        _ensure_mock_module("timm")


_setup_insightface_mocks()
_setup_mediapipe_mocks()
_setup_torch_mocks()

# Ensure jetson root and service dirs are on path
sys.path.insert(0, str(JETSON_ROOT))
for svc_dir in (JETSON_ROOT / "services").iterdir():
    if svc_dir.is_dir():
        sys.path.insert(0, str(svc_dir))


# ---------------------------------------------------------------------------
# Fake camera frame (640x480 BGR)
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def fake_frame_bytes(fake_frame):
    """JPEG-encoded bytes of the fake frame."""
    import cv2
    _, buf = cv2.imencode(".jpg", fake_frame)
    return buf.tobytes()


@pytest.fixture
def fake_frame_b64(fake_frame_bytes):
    """Base64-encoded JPEG string."""
    import base64
    return base64.b64encode(fake_frame_bytes).decode("utf-8")


# ---------------------------------------------------------------------------
# Eyes service app
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def eyes_client():
    from services.eyes.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Thermal service app
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def thermal_client():
    from services.thermal.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Skin service app (model loading mocked out)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def skin_client():
    import services.skin.main as skin_mod
    original = skin_mod._inference_system
    skin_mod._inference_system = None
    try:
        transport = ASGITransport(app=skin_mod.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        skin_mod._inference_system = original


# ---------------------------------------------------------------------------
# Mock InsightFace face result
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_insightface_face():
    """A minimal mock of an InsightFace detected face object."""
    face = MagicMock()
    face.det_score = 0.99
    face.bbox = np.array([100.0, 100.0, 200.0, 200.0])
    face.kps = np.array(
        [[120, 120], [180, 120], [150, 150], [130, 170], [170, 170]],
        dtype=np.float32,
    )
    emb = np.random.randn(512).astype(np.float32)
    emb /= np.linalg.norm(emb)
    face.normed_embedding = emb
    return face


# ---------------------------------------------------------------------------
# Face service app (InsightFace mocked)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def face_client(mock_insightface_face):
    import services.face.main as face_mod

    mock_face_app = MagicMock()
    mock_face_app.get.return_value = [mock_insightface_face]

    original = face_mod.face_app
    face_mod.face_app = mock_face_app
    try:
        transport = ASGITransport(app=face_mod.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        face_mod.face_app = original


@pytest_asyncio.fixture
async def face_client_no_face():
    """Face client where InsightFace detects no faces."""
    import services.face.main as face_mod

    mock_face_app = MagicMock()
    mock_face_app.get.return_value = []

    original = face_mod.face_app
    face_mod.face_app = mock_face_app
    try:
        transport = ASGITransport(app=face_mod.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        face_mod.face_app = original
