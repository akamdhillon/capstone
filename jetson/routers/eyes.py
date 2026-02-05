"""
Eye Strain API Router (Port 8004)
=================================
Endpoints for blink rate and eye redness analysis.
"""

import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from services.eye_strain import EyeStrainService
from services.camera import get_camera_manager

logger = logging.getLogger("clarity-ml.router.eyes")

router = APIRouter()

# Service instance
_service: Optional[EyeStrainService] = None


def get_service() -> EyeStrainService:
    """Get or create the eye strain service instance."""
    global _service
    if _service is None:
        _service = EyeStrainService()
        _service.initialize()
    return _service


# =============================================================================
# Request/Response Models
# =============================================================================

class EyeStrainResponse(BaseModel):
    """Eye strain analysis response."""
    face_detected: bool
    eye_aspect_ratio: Optional[dict] = None
    blink_analysis: Optional[dict] = None
    redness_analysis: Optional[dict] = None
    strain_score: Optional[float] = None
    strain_level: Optional[str] = None
    inference_time_ms: float = 0
    error: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/")
async def root():
    """Eye strain service info."""
    return {
        "service": "Eye Strain",
        "port": 8004,
        "model": "MediaPipe Face Mesh (468 landmarks)",
        "metrics": [
            "eye_aspect_ratio",
            "blink_rate",
            "sclera_redness"
        ],
        "normal_blink_rate": "15-20 blinks/minute"
    }


@router.post("/analyze", response_model=EyeStrainResponse)
async def analyze_eyes(file: UploadFile = File(...)):
    """
    Analyze eye strain metrics from an uploaded image.
    
    Returns EAR, blink detection, and redness analysis.
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
            return EyeStrainResponse(
                face_detected=False,
                error=result["error"],
                inference_time_ms=result.get("inference_time_ms", 0)
            )
        
        return EyeStrainResponse(
            face_detected=result.get("face_detected", False),
            eye_aspect_ratio=result.get("eye_aspect_ratio"),
            blink_analysis=result.get("blink_analysis"),
            redness_analysis=result.get("redness_analysis"),
            strain_score=result.get("strain_score"),
            strain_level=result.get("strain_level"),
            inference_time_ms=result.get("inference_time_ms", 0)
        )
        
    except Exception as e:
        logger.error(f"Eye analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-live")
async def analyze_from_camera(camera: str = "primary"):
    """
    Analyze eye strain from live camera feed.
    
    Continuous monitoring recommended for accurate blink rate.
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


@router.post("/reset-blinks")
async def reset_blink_counter():
    """
    Reset the blink counter for a new session.
    
    Call this when starting a new monitoring session.
    """
    service = get_service()
    service.reset_blink_counter()
    
    return {
        "success": True,
        "message": "Blink counter reset"
    }


@router.get("/blink-stats")
async def get_blink_stats():
    """
    Get current blink statistics without new analysis.
    """
    service = get_service()
    
    if not service.is_initialized:
        return {
            "initialized": False,
            "message": "Service not yet initialized"
        }
    
    return {
        "initialized": True,
        "total_blinks": service._blink_counter,
        "frames_analyzed": service._frame_counter,
        "thresholds": {
            "ear_threshold": EyeStrainService.EAR_THRESHOLD,
            "normal_blink_rate_min": EyeStrainService.NORMAL_BLINK_RATE_MIN,
            "normal_blink_rate_max": EyeStrainService.NORMAL_BLINK_RATE_MAX
        }
    }
