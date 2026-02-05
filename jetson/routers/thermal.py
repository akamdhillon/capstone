"""
Thermal Service API Router (Port 8005)
======================================
Ghost Service - Returns null when ENABLE_THERMAL=false.
"""

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.thermal import ThermalService
from config import settings

logger = logging.getLogger("clarity-ml.router.thermal")

router = APIRouter()

# Service instance
_service: Optional[ThermalService] = None


def get_service() -> ThermalService:
    """Get or create the thermal service instance."""
    global _service
    if _service is None:
        _service = ThermalService()
        _service.initialize()
    return _service


# =============================================================================
# Request/Response Models
# =============================================================================

class ThermalResponse(BaseModel):
    """Thermal reading response."""
    enabled: bool
    temperature: Optional[float] = None
    unit: str = "celsius"
    face_temperature: Optional[float] = None
    ambient_temperature: Optional[float] = None
    thermal_map: Optional[list] = None
    message: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/")
async def root():
    """Thermal service info (ghost service)."""
    return {
        "service": "Thermal",
        "port": 8005,
        "enabled": settings.ENABLE_THERMAL,
        "type": "Ghost Service" if not settings.ENABLE_THERMAL else "Active",
        "description": "Returns null values when disabled to maintain API compatibility"
    }


@router.get("/read", response_model=ThermalResponse)
async def read_thermal():
    """
    Read thermal sensor data.
    
    Returns null values when ENABLE_THERMAL=false (ghost service mode).
    This ensures the orchestrator's wellness score logic doesn't break.
    """
    service = get_service()
    result = service.read()
    
    return ThermalResponse(
        enabled=result.get("enabled", False),
        temperature=result.get("temperature"),
        unit=result.get("unit", "celsius"),
        face_temperature=result.get("face_temperature"),
        ambient_temperature=result.get("ambient_temperature"),
        thermal_map=result.get("thermal_map"),
        message=result.get("message"),
        error=result.get("error")
    )


@router.get("/status")
async def get_status():
    """
    Get thermal service status.
    
    Shows whether the service is enabled and initialized.
    """
    service = get_service()
    
    return {
        "enabled": service.is_enabled,
        "initialized": service.is_initialized,
        "mode": "ghost" if not service.is_enabled else "active",
        "env_variable": "ENABLE_THERMAL",
        "current_value": settings.ENABLE_THERMAL
    }


@router.get("/null-response")
async def get_null_response():
    """
    Get the standard null response structure.
    
    Useful for orchestrator to understand the expected format
    when thermal is disabled.
    """
    return ThermalService.get_null_response()
