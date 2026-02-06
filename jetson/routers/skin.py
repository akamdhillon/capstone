"""
Skin Analysis API Router (Port 8002)
====================================
Endpoints for YOLOv8-based skin condition detection.
"""

import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from services.skin_analysis import SkinAnalysisService
from services.camera import get_camera_manager

logger = logging.getLogger("clarity-ml.router.skin")

router = APIRouter()

# Service instance
_service: Optional[SkinAnalysisService] = None


def get_service() -> SkinAnalysisService:
    """Get or create the skin analysis service instance."""
    global _service
    if _service is None:
        _service = SkinAnalysisService()
        _service.initialize()
    return _service


# =============================================================================
# Request/Response Models
# =============================================================================

class AnalysisResponse(BaseModel):
    """Skin analysis response."""
    success: bool
    detections: list
    summary: dict
    count: int
    inference_time_ms: float
    using_tensorrt: bool
    error: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/")
async def root():
    """Skin analysis service info."""
    return {
        "service": "Skin Analysis",
        "port": 8002,
        "model": "YOLOv8n (TensorRT FP16)",
        "classes": ["acne_inflammatory", "acne_non_inflammatory", "wrinkle", "dark_spot"],
        "target_latency_ms": 200
    }


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_skin(
    file: UploadFile = File(...),
    confidence: float = 0.5
):
    """
    Analyze skin conditions in an uploaded image.
    
    Detects: Acne (inflammatory/non-inflammatory), Wrinkles, Dark Spots
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
        result = service.analyze(image, confidence_threshold=confidence)
        
        if "error" in result and result["error"]:
            return AnalysisResponse(
                success=False,
                detections=[],
                summary={},
                count=0,
                inference_time_ms=0,
                using_tensorrt=False,
                error=result["error"]
            )
        
        return AnalysisResponse(
            success=True,
            detections=result.get("detections", []),
            summary=result.get("summary", {}),
            count=result.get("count", 0),
            inference_time_ms=result.get("inference_time_ms", 0),
            using_tensorrt=result.get("using_tensorrt", False)
        )
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-live")
async def analyze_from_camera(
    camera: str = "primary",
    confidence: float = 0.5
):
    """
    Analyze skin conditions from live camera feed.
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
        result = service.analyze(frame, confidence_threshold=confidence)
        
        # Calculate score: Higher = better skin health
        # Invert severity: 0 severity = 100 score
        severity = result.get("summary", {}).get("severity_score", 0)
        score = max(0, 100 - severity)
        
        return {
            "success": "error" not in result,
            "score": score,
            "detections": result.get("detections", []),
            "summary": result.get("summary", {}),
            "count": result.get("count", 0),
            "camera": camera,
            "timestamp": timestamp,
            "inference_time_ms": result.get("inference_time_ms", 0),
            "using_tensorrt": result.get("using_tensorrt", False)
        }
        
    except Exception as e:
        logger.error(f"Live analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/classes")
async def get_detection_classes():
    """Get list of detectable skin condition classes."""
    return {
        "classes": SkinAnalysisService.CLASSES,
        "descriptions": {
            "acne_inflammatory": "Red, swollen acne (pustules, papules, cysts)",
            "acne_non_inflammatory": "Blackheads and whiteheads",
            "wrinkle": "Fine lines and wrinkles",
            "dark_spot": "Hyperpigmentation and dark spots"
        }
    }
