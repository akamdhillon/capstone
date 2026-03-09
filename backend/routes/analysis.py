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
from debug_events import frame_poller_context, emit_debug_event

JETSON_CAPTURE_URL = f"http://{settings.JETSON_IP}:8001/capture-frame"
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
    await emit_debug_event({"type": "progress", "phase": "capturing", "service": "full", "message": "Capturing frame for full scan...", "elapsed_ms": 0})
    
    image = request.image if request else None
    client = JetsonClient()
    async with frame_poller_context(JETSON_CAPTURE_URL):
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


# =============================================================================
# INDIVIDUAL SERVICE ENDPOINTS
# =============================================================================

class SingleServiceRequest(BaseModel):
    image: Optional[str] = None  # base64-encoded JPEG from frontend webcam
    user_id: Optional[str] = None


@router.post("/debug/eyes")
async def debug_eye_analysis(request: SingleServiceRequest = None):
    """Run eye strain analysis via Jetson: 5s camera stream, EAR + blink rate + score. Saves result and shows debug feed."""
    import time
    import httpx

    start_time = time.time()
    user_id = getattr(request, "user_id", None) or "unknown"
    await emit_debug_event({"type": "progress", "phase": "capturing", "service": "eyes", "message": "Capturing frames for eye analysis (5s)...", "elapsed_ms": 0})

    orchestrator_url = f"http://{settings.JETSON_IP}:8001"
    result = None
    async with frame_poller_context(JETSON_CAPTURE_URL):
        async with httpx.AsyncClient(timeout=35.0) as client:
            response = await client.post(
                f"{orchestrator_url}/eyes/run",
                json={"user_id": user_id},
            )
            if response.status_code == 200:
                result = response.json()
            else:
                result = {"error": f"HTTP {response.status_code}", "score": None, "details": None}

    elapsed_ms = (time.time() - start_time) * 1000
    success = result and result.get("score") is not None and not result.get("error")
    score = result.get("score") if result else None
    details = result.get("details") if result else None
    captured_image = result.get("captured_image") if result else None
    errors = [result["error"]] if result and result.get("error") else []

    # Save to eye results history
    if success and score is not None:
        try:
            base_url = settings.BACKEND_BASE_URL or "http://localhost:8000"
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{base_url}/api/eyes/results",
                    json={"score": float(score), "details": details, "user_id": user_id},
                )
        except Exception as e:
            logger.warning(f"Failed to save eye result: {e}")

    return {
        "success": success,
        "score": score,
        "details": details,
        "captured_image": captured_image,
        "errors": errors,
        "timing_ms": elapsed_ms,
    }


@router.post("/debug/skin")
async def debug_skin_analysis(request: SingleServiceRequest = None):
    """Run skin analysis only via Jetson skin service."""
    import time
    import httpx

    start_time = time.time()
    image = request.image if request else None

    # Use the full orchestrator which captures an image and calls all services,
    # then extract only the skin results
    client = JetsonClient()
    ml_results = await client.run_full_analysis(image=image)

    elapsed_ms = (time.time() - start_time) * 1000

    return {
        "success": ml_results.skin_score is not None,
        "score": ml_results.skin_score,
        "details": ml_results.skin_details,
        "captured_image": ml_results.captured_image,
        "errors": [e for e in ml_results.errors if "skin" in e.lower()] if ml_results.errors else [],
        "timing_ms": elapsed_ms,
    }
