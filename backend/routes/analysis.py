# =============================================================================
# CLARITY+ BACKEND - ANALYSIS ROUTES
# =============================================================================
"""
API routes for wellness analysis operations.
Stateless - Pass-through to Jetson and Scoring Engine.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import settings
from models import AnalysisRequest, AnalysisResult
from services.wellness import WellnessService
from services.jetson_client import JetsonClient
from services.wellness_scoring import WellnessScoringEngine

logger = logging.getLogger(__name__)
router = APIRouter()
# settings = get_settings() # Removed, imported directly


@router.post("/analyze", response_model=AnalysisResult)
async def trigger_analysis(
    request: AnalysisRequest
):
    """Trigger a full wellness analysis pipeline (Stateless)."""
    service = WellnessService()
    
    try:
        result = await service.perform_analysis(request.user_id)
        logger.info(f"Analysis completed for user {request.user_id}: score={result.overall_score}")
        return result
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jetson/health")
async def check_jetson_health():
    """Check health status of all Jetson ML services."""
    client = JetsonClient()
    health = await client.health_check()
    all_healthy = all(health.values())
    
    return {
        "status": "ok" if all_healthy else "degraded",
        "services": health,
        "thermal_enabled": settings.THERMAL_ENABLED
    }


# =============================================================================
# DEBUG ENDPOINTS
# =============================================================================

@router.get("/debug")
async def debug_info():
    """Debug endpoint for connectivity."""
    import platform
    import sys
    import httpx
    
    client = JetsonClient()
    connectivity = {}
    errors = {}
    
    services = [
        ("face_recognition", settings.JETSON_FACE_PORT, "/health"),
        ("skin_analysis", settings.JETSON_SKIN_PORT, "/health"),
        ("posture", settings.JETSON_POSTURE_PORT, "/health"),
        ("eye_strain", settings.JETSON_EYE_PORT, "/health"),
        ("thermal", settings.JETSON_THERMAL_PORT, "/health"),
    ]
    
    for name, port, endpoint in services:
        url = f"http://{settings.JETSON_IP}:{port}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=3.0) as http_client:
                response = await http_client.get(url)
                connectivity[name] = {"reachable": True, "status_code": response.status_code, "url": url}
        except Exception as e:
            connectivity[name] = {"reachable": False, "url": url}
            errors[name] = str(e)
            
    return {
        "platform": {"system": platform.system(), "python_version": sys.version},
        "configuration": {
            "jetson_ip": settings.JETSON_IP,
            "rpi_ip": settings.RPI_IP,
            "weights": settings.weights
        },
        "connectivity": connectivity,
        "errors": errors if errors else None
    }


class DebugAnalyzeRequest(BaseModel):
    image: Optional[str] = None  # base64-encoded JPEG from frontend webcam


@router.post("/debug/analyze")
async def debug_analyze(request: DebugAnalyzeRequest = None):
    """
    Debug analysis without saving to DB.
    Accepts an optional base64 webcam image from the frontend.
    """
    import time
    start_time = time.time()
    
    image = request.image if request else None
    client = JetsonClient()
    ml_results = await client.run_full_analysis(image=image)
    
    engine = WellnessScoringEngine()
    overall_score, weights_used = engine.calculate(
        skin_score=ml_results.skin_score,
        posture_score=ml_results.posture_score,
        eye_score=ml_results.eye_score,
        thermal_score=ml_results.thermal_score
    )
    
    elapsed_ms = (time.time() - start_time) * 1000
    
    return {
        "success": len(ml_results.errors) == 0,
        "scores": {
            "skin": ml_results.skin_score,
            "posture": ml_results.posture_score,
            "eyes": ml_results.eye_score,
            "thermal": ml_results.thermal_score
        },
        "overall_score": overall_score,
        "captured_image": ml_results.captured_image,
        "details": {
            "skin": ml_results.skin_details,
            "posture": ml_results.posture_details,
            "eyes": ml_results.eye_details,
            "thermal": ml_results.thermal_details
        },
        "errors": ml_results.errors,
        "timing_ms": elapsed_ms
    }
