"""Routers module for Clarity+ ML service endpoints."""
from .face import router as face_router
from .skin import router as skin_router
from .posture import router as posture_router
from .eyes import router as eyes_router
from .thermal import router as thermal_router

__all__ = [
    "face_router",
    "skin_router",
    "posture_router",
    "eyes_router",
    "thermal_router",
]
