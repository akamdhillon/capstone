"""
Face Recognition API Router (Port 8001)
=======================================
Endpoints for face detection and embedding generation.
"""

import logging
from typing import Optional
import base64
import io

import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from services.face_recognition import FaceRecognitionService
from services.camera import get_camera_manager

logger = logging.getLogger("clarity-ml.router.face")

router = APIRouter()

# Service instance (lazy initialization)
_service: Optional[FaceRecognitionService] = None


def get_service() -> FaceRecognitionService:
    """Get or create the face recognition service instance."""
    global _service
    if _service is None:
        _service = FaceRecognitionService()
        _service.initialize()
    return _service


# =============================================================================
# Request/Response Models
# =============================================================================

class DetectionResponse(BaseModel):
    """Face detection response."""
    faces_detected: int
    faces: list
    inference_time_ms: float


class EmbeddingResponse(BaseModel):
    """Face embedding response."""
    success: bool
    embedding: Optional[list] = None
    embedding_dim: Optional[int] = None
    facial_area: Optional[dict] = None
    inference_time_ms: float
    error: Optional[str] = None


class CompareRequest(BaseModel):
    """Embedding comparison request."""
    embedding1: list = Field(..., description="First 512-dim embedding")
    embedding2: list = Field(..., description="Second 512-dim embedding")
    threshold: float = Field(default=0.4, description="Match threshold")


class CompareResponse(BaseModel):
    """Embedding comparison response."""
    is_match: bool
    distance: float
    cosine_similarity: float
    threshold: float


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/")
async def root():
    """Face recognition service info."""
    return {
        "service": "Face Recognition",
        "port": 8001,
        "model": "DeepFace (RetinaFace + FaceNet512)",
        "target_latency_ms": 100
    }


@router.post("/detect", response_model=DetectionResponse)
async def detect_faces(file: UploadFile = File(...)):
    """
    Detect faces in an uploaded image.
    
    Returns list of detected faces with bounding boxes.
    """
    try:
        import cv2
        
        # Read image from upload
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Run detection
        service = get_service()
        faces = service.detect_faces(image)
        
        # Convert numpy types for JSON serialization
        serializable_faces = []
        for face in faces:
            serializable_faces.append({
                "confidence": float(face.get("confidence", 0)),
                "facial_area": face.get("facial_area", {})
            })
        
        return DetectionResponse(
            faces_detected=len(faces),
            faces=serializable_faces,
            inference_time_ms=service.last_inference_time_ms
        )
        
    except Exception as e:
        logger.error(f"Detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed", response_model=EmbeddingResponse)
async def generate_embedding(file: UploadFile = File(...)):
    """
    Generate 512-dimensional face embedding from an image.
    
    The image should contain exactly one face for best results.
    """
    try:
        import cv2
        
        # Read image from upload
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Generate embedding
        service = get_service()
        result = service.generate_embedding(image)
        
        if result is None:
            return EmbeddingResponse(
                success=False,
                inference_time_ms=service.last_inference_time_ms,
                error="No face detected or embedding failed"
            )
        
        return EmbeddingResponse(
            success=True,
            embedding=result.get("embedding", []),
            embedding_dim=result.get("embedding_dim", 0),
            facial_area=result.get("facial_area"),
            inference_time_ms=result.get("inference_time_ms", 0)
        )
        
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare", response_model=CompareResponse)
async def compare_embeddings(request: CompareRequest):
    """
    Compare two face embeddings for similarity.
    
    Lower distance = better match.
    """
    try:
        service = get_service()
        result = service.compare_embeddings(
            request.embedding1,
            request.embedding2,
            request.threshold
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return CompareResponse(
            is_match=result["is_match"],
            distance=result["distance"],
            cosine_similarity=result["cosine_similarity"],
            threshold=result["threshold"]
        )
        
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect-live")
async def detect_from_camera(camera: str = "primary"):
    """
    Detect faces from live camera feed.
    
    Uses the most recent frame from the camera manager.
    """
    try:
        camera_manager = get_camera_manager()
        
        if not camera_manager.is_running:
            camera_manager.start()
        
        frame, timestamp = camera_manager.get_frame(camera)
        
        if frame is None:
            raise HTTPException(
                status_code=503,
                detail=f"No frame available from {camera} camera"
            )
        
        service = get_service()
        faces = service.detect_faces(frame)
        
        return {
            "faces_detected": len(faces),
            "faces": [
                {
                    "confidence": float(f.get("confidence", 0)),
                    "facial_area": f.get("facial_area", {})
                }
                for f in faces
            ],
            "camera": camera,
            "timestamp": timestamp,
            "inference_time_ms": service.last_inference_time_ms
        }
        
    except Exception as e:
        logger.error(f"Live detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
