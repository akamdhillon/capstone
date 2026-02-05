"""
Posture Analysis API Router (Port 8003)
=======================================
Endpoints for MediaPipe Pose-based posture analysis.
"""

import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from services.posture import PostureService
from services.camera import get_camera_manager

logger = logging.getLogger("clarity-ml.router.posture")

router = APIRouter()

# Service instance
_service: Optional[PostureService] = None


def get_service() -> PostureService:
    """Get or create the posture service instance."""
    global _service
    if _service is None:
        _service = PostureService()
        _service.initialize()
    return _service


# =============================================================================
# Request/Response Models
# =============================================================================

class PostureResponse(BaseModel):
    """Posture analysis response."""
    pose_detected: bool
    posture_score: Optional[float] = None
    head_forward_angle: Optional[float] = None
    slouch_angle: Optional[float] = None
    shoulder_alignment: Optional[dict] = None
    issues: list = []
    is_good_posture: bool = False
    inference_time_ms: float = 0
    error: Optional[str] = None


class LandmarksResponse(BaseModel):
    """Pose landmarks response."""
    landmarks_detected: bool
    landmarks: Optional[list] = None
    count: int = 0


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/")
async def root():
    """Posture service info."""
    return {
        "service": "Posture Detection",
        "port": 8003,
        "model": "MediaPipe Pose (BlazePose GHUM)",
        "landmarks_count": 33,
        "metrics": ["head_forward_angle", "slouch_angle", "shoulder_alignment"]
    }


@router.post("/analyze", response_model=PostureResponse)
async def analyze_posture(file: UploadFile = File(...)):
    """
    Analyze posture in an uploaded image.
    
    Returns posture score, head forward angle, slouch detection,
    and shoulder alignment analysis.
    """
    try:
        import cv2
        
        # Read image from upload
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Run analysis
        service = get_service()
        result = service.analyze(image)
        
        if "error" in result:
            return PostureResponse(
                pose_detected=False,
                error=result["error"],
                inference_time_ms=result.get("inference_time_ms", 0)
            )
        
        return PostureResponse(
            pose_detected=result.get("pose_detected", False),
            posture_score=result.get("posture_score"),
            head_forward_angle=result.get("head_forward_angle"),
            slouch_angle=result.get("slouch_angle"),
            shoulder_alignment=result.get("shoulder_alignment"),
            issues=result.get("issues", []),
            is_good_posture=result.get("is_good_posture", False),
            inference_time_ms=result.get("inference_time_ms", 0)
        )
        
    except Exception as e:
        logger.error(f"Posture analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-live")
async def analyze_from_camera(camera: str = "primary"):
    """
    Analyze posture from live camera feed.
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
        result = service.analyze(frame)
        
        result["camera"] = camera
        result["timestamp"] = timestamp
        
        return result
        
    except Exception as e:
        logger.error(f"Live analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/landmarks", response_model=LandmarksResponse)
async def get_landmarks(file: UploadFile = File(...)):
    """
    Get all 33 pose landmarks from an image.
    
    Returns normalized coordinates for visualization.
    """
    try:
        import cv2
        
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        service = get_service()
        landmarks = service.get_landmark_positions(image)
        
        if landmarks is None:
            return LandmarksResponse(
                landmarks_detected=False,
                count=0
            )
        
        return LandmarksResponse(
            landmarks_detected=True,
            landmarks=landmarks,
            count=len(landmarks)
        )
        
    except Exception as e:
        logger.error(f"Landmark extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/thresholds")
async def get_thresholds():
    """Get posture analysis thresholds."""
    return {
        "head_forward_threshold_deg": PostureService.HEAD_FORWARD_THRESHOLD_DEG,
        "slouch_threshold_deg": PostureService.SLOUCH_THRESHOLD_DEG,
        "description": {
            "head_forward": "Angle deviation from vertical alignment (ear to shoulder)",
            "slouch": "Thoracic spine angle (shoulder to hip vertical deviation)"
        }
    }
