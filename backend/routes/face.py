# =============================================================================
# CLARITY+ BACKEND - FACE RECOGNITION ROUTES
# =============================================================================
"""
Proxy routes for face detection, enrollment, and recognition.
Forwards requests to the Jetson face service and manages local user storage.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FACE_SERVICE_URL = f"http://{settings.JETSON_IP}:{settings.JETSON_FACE_PORT}"
FACE_USERS_FILE = Path(__file__).resolve().parent.parent / "data" / "face_users.json"
REQUEST_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class DetectRequest(BaseModel):
    image: str  # base64


class EnrollRequest(BaseModel):
    name: str
    images: List[str]  # base64 images (5-10)


class RecognizeRequest(BaseModel):
    image: str  # base64


# ---------------------------------------------------------------------------
# Storage helpers (simple JSON file)
# ---------------------------------------------------------------------------
def _load_users() -> dict:
    """Load enrolled users from JSON file."""
    if FACE_USERS_FILE.exists():
        try:
            return json.loads(FACE_USERS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_users(users: dict):
    """Save enrolled users to JSON file."""
    FACE_USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    FACE_USERS_FILE.write_text(json.dumps(users, indent=2))


# ---------------------------------------------------------------------------
# Helper to call face service
# ---------------------------------------------------------------------------
async def _call_face_service(endpoint: str, payload: dict) -> dict:
    """Forward a request to the Jetson face service."""
    url = f"{FACE_SERVICE_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to face service at {url}"
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Face service timed out"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Face service error: {e.response.text}"
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/face/detect")
async def detect_face(request: DetectRequest):
    """Proxy to Jetson face detection."""
    return await _call_face_service("/face/detect", {"image": request.image})


@router.post("/face/enroll")
async def enroll_face(request: EnrollRequest):
    """
    Enroll a new face:
    1. Call Jetson /face/enroll with images
    2. Store name + embedding locally
    3. Return user info
    """
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    if len(request.images) < 2:
        raise HTTPException(status_code=400, detail="At least 2 images required")

    # Call Jetson face service
    result = await _call_face_service("/face/enroll", {"images": request.images})

    embedding = result.get("embedding")
    if not embedding:
        raise HTTPException(status_code=500, detail="Face service did not return an embedding")

    # Create user and store
    user_id = str(uuid.uuid4())
    users = _load_users()
    users[user_id] = {
        "name": request.name.strip(),
        "embedding": embedding,
        "quality_score": result.get("quality_score", 0),
        "faces_processed": result.get("faces_processed", 0),
    }
    _save_users(users)

    logger.info(f"Enrolled user '{request.name}' as {user_id} (quality={result.get('quality_score')})")

    return {
        "success": True,
        "user_id": user_id,
        "name": request.name.strip(),
        "quality_score": result.get("quality_score"),
        "faces_processed": result.get("faces_processed"),
        "latency_ms": result.get("latency_ms"),
    }


@router.post("/face/recognize")
async def recognize_face(request: RecognizeRequest):
    """
    Recognize a face:
    1. Load all enrolled embeddings
    2. Call Jetson /face/recognize with image + known embeddings
    3. Return match result with user name
    """
    users = _load_users()

    if not users:
        return {
            "match": False,
            "message": "No enrolled users. Please enroll first.",
            "user_id": None,
            "name": None,
            "confidence": 0,
            "match_type": "no_users",
        }

    # Build known_embeddings payload
    known_embeddings = [
        {"user_id": uid, "embedding": data["embedding"]}
        for uid, data in users.items()
    ]

    result = await _call_face_service("/face/recognize", {
        "image": request.image,
        "known_embeddings": known_embeddings,
    })

    # Enrich with user name
    matched_id = result.get("user_id")
    matched_name = None
    if matched_id and matched_id in users:
        matched_name = users[matched_id]["name"]

    return {
        "match": result.get("match", False),
        "user_id": matched_id,
        "name": matched_name,
        "confidence": result.get("confidence", 0),
        "match_type": result.get("match_type", "unknown"),
        "latency_ms": result.get("latency_ms"),
    }


@router.get("/face/users")
async def list_face_users():
    """List all enrolled users (without embeddings)."""
    users = _load_users()
    return {
        "users": [
            {"user_id": uid, "name": data["name"], "quality_score": data.get("quality_score")}
            for uid, data in users.items()
        ]
    }
