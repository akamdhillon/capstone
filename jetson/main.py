"""
Clarity+ Jetson ML Service Layer - Main Entry Point
====================================================
Launches all ML inference services as FastAPI applications.
Each service runs on its designated port (8001-8005).

Services:
    - Port 8001: Face Recognition (DeepFace)
    - Port 8002: Skin Analysis (YOLOv8)
    - Port 8003: Posture Detection (MediaPipe)
    - Port 8004: Eye Strain Analysis (EAR)
    - Port 8005: Thermal (Ghost Service - returns null when disabled)
"""

import asyncio
import logging
import signal
import sys
from typing import List

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("clarity-ml")


def create_app(service_name: str) -> FastAPI:
    """Create a FastAPI application for a specific service."""
    app = FastAPI(
        title=f"Clarity+ {service_name}",
        description=f"ML inference endpoint for {service_name}",
        version="1.0.0"
    )
    
    # CORS middleware for cross-origin requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


# =============================================================================
# SERVICE APPLICATIONS
# =============================================================================

# Face Recognition Service (Port 8001)
face_app = create_app("Face Recognition")

# Skin Analysis Service (Port 8002)
skin_app = create_app("Skin Analysis")

# Posture Service (Port 8003)
posture_app = create_app("Posture Detection")

# Eye Strain Service (Port 8004)
eye_app = create_app("Eye Strain")

# Thermal Service (Port 8005) - Ghost Service
thermal_app = create_app("Thermal")


# =============================================================================
# ROUTER IMPORTS & MOUNTING
# =============================================================================

def setup_routers():
    """Import and mount all service routers."""
    from routers import face, skin, posture, eyes, thermal
    
    face_app.include_router(face.router, tags=["Face Recognition"])
    skin_app.include_router(skin.router, tags=["Skin Analysis"])
    posture_app.include_router(posture.router, tags=["Posture"])
    eye_app.include_router(eyes.router, tags=["Eye Strain"])
    thermal_app.include_router(thermal.router, tags=["Thermal"])


# =============================================================================
# HEALTH CHECK ENDPOINTS
# =============================================================================

@face_app.get("/health")
async def face_health():
    """Health check for Face Recognition service."""
    return {"status": "healthy", "service": "face_recognition", "port": 8001}


@skin_app.get("/health")
async def skin_health():
    """Health check for Skin Analysis service."""
    return {"status": "healthy", "service": "skin_analysis", "port": 8002}


@posture_app.get("/health")
async def posture_health():
    """Health check for Posture service."""
    return {"status": "healthy", "service": "posture", "port": 8003}


@eye_app.get("/health")
async def eye_health():
    """Health check for Eye Strain service."""
    return {"status": "healthy", "service": "eye_strain", "port": 8004}


@thermal_app.get("/health")
async def thermal_health():
    """Health check for Thermal service (ghost service)."""
    return {
        "status": "healthy",
        "service": "thermal",
        "port": 8005,
        "enabled": settings.ENABLE_THERMAL
    }


# =============================================================================
# DEBUG ENDPOINTS (For troubleshooting)
# =============================================================================

def get_debug_info():
    """Get common debug information for all services."""
    import platform
    import sys
    import os
    from config import IS_MAC, IS_LINUX
    
    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": sys.version,
            "is_mac": IS_MAC,
            "is_linux": IS_LINUX
        },
        "settings": {
            "dev_mode": settings.DEV_MODE,
            "enable_thermal": settings.ENABLE_THERMAL,
            "model_precision": settings.MODEL_PRECISION,
            "host": settings.HOST,
            "camera_primary": str(settings.camera_source_primary),
            "camera_secondary": str(settings.camera_source_secondary),
            "use_gstreamer": settings.USE_GSTREAMER,
            "dev_video_path": settings.DEV_VIDEO_PATH if settings.DEV_MODE else None
        },
        "ports": {
            "face_recognition": settings.FACE_RECOGNITION_PORT,
            "skin_analysis": settings.SKIN_ANALYSIS_PORT,
            "posture": settings.POSTURE_PORT,
            "eye_strain": settings.EYE_STRAIN_PORT,
            "thermal": settings.THERMAL_PORT
        }
    }


@face_app.get("/debug")
async def face_debug():
    """Debug info for Face Recognition service."""
    from services.camera import get_camera_manager
    from routers.face import _service
    
    camera = get_camera_manager()
    
    return {
        **get_debug_info(),
        "service": "face_recognition",
        "service_initialized": _service.is_initialized if _service else False,
        "camera": {
            "running": camera.is_running,
            "width": camera.width,
            "height": camera.height,
            "fps": camera.fps
        }
    }


@skin_app.get("/debug")
async def skin_debug():
    """Debug info for Skin Analysis service."""
    from services.camera import get_camera_manager
    from routers.skin import _service
    
    camera = get_camera_manager()
    
    return {
        **get_debug_info(),
        "service": "skin_analysis",
        "service_initialized": _service.is_initialized if _service else False,
        "using_tensorrt": _service._using_tensorrt if _service else False,
        "camera": {
            "running": camera.is_running
        }
    }


@posture_app.get("/debug")
async def posture_debug():
    """Debug info for Posture service."""
    from services.camera import get_camera_manager
    from routers.posture import _service
    
    camera = get_camera_manager()
    
    return {
        **get_debug_info(),
        "service": "posture",
        "service_initialized": _service.is_initialized if _service else False,
        "camera": {
            "running": camera.is_running
        }
    }


@eye_app.get("/debug")
async def eye_debug():
    """Debug info for Eye Strain service."""
    from services.camera import get_camera_manager
    from routers.eyes import _service
    
    camera = get_camera_manager()
    
    return {
        **get_debug_info(),
        "service": "eye_strain",
        "service_initialized": _service.is_initialized if _service else False,
        "camera": {
            "running": camera.is_running
        }
    }


@thermal_app.get("/debug")
async def thermal_debug():
    """Debug info for Thermal service."""
    from routers.thermal import _service
    
    return {
        **get_debug_info(),
        "service": "thermal",
        "service_enabled": settings.ENABLE_THERMAL,
        "service_initialized": _service.is_initialized if _service else False
    }



# =============================================================================
# MULTI-SERVICE RUNNER
# =============================================================================

class ServiceRunner:
    """Manages multiple Uvicorn servers running concurrently."""
    
    def __init__(self):
        self.servers: List[uvicorn.Server] = []
        self.tasks: List[asyncio.Task] = []
    
    def add_service(self, app: FastAPI, port: int, name: str):
        """Add a service to be run."""
        config = uvicorn.Config(
            app=app,
            host=settings.HOST,
            port=port,
            log_level="info",
            access_log=True
        )
        server = uvicorn.Server(config)
        self.servers.append((server, name, port))
    
    async def run_all(self):
        """Run all registered services concurrently."""
        async def run_server(server, name, port):
            logger.info(f"Starting {name} on port {port}")
            await server.serve()
        
        self.tasks = [
            asyncio.create_task(run_server(server, name, port))
            for server, name, port in self.servers
        ]
        
        await asyncio.gather(*self.tasks, return_exceptions=True)
    
    async def shutdown(self):
        """Gracefully shutdown all servers."""
        logger.info("Shutting down all services...")
        for server, name, _ in self.servers:
            server.should_exit = True
        
        for task in self.tasks:
            task.cancel()


async def main():
    """Main entry point for the ML service layer."""
    logger.info("=" * 60)
    logger.info("CLARITY+ JETSON ML SERVICE LAYER")
    logger.info("=" * 60)
    logger.info(f"DEV_MODE: {settings.DEV_MODE}")
    logger.info(f"ENABLE_THERMAL: {settings.ENABLE_THERMAL}")
    logger.info(f"MODEL_PRECISION: {settings.MODEL_PRECISION}")
    logger.info("=" * 60)
    
    # Setup routers
    setup_routers()
    
    # Initialize service runner
    runner = ServiceRunner()
    
    # Register all services
    runner.add_service(face_app, settings.FACE_RECOGNITION_PORT, "Face Recognition")
    runner.add_service(skin_app, settings.SKIN_ANALYSIS_PORT, "Skin Analysis")
    runner.add_service(posture_app, settings.POSTURE_PORT, "Posture Detection")
    runner.add_service(eye_app, settings.EYE_STRAIN_PORT, "Eye Strain")
    runner.add_service(thermal_app, settings.THERMAL_PORT, "Thermal (Ghost Service)")
    
    # Setup graceful shutdown
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(runner.shutdown())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    # Run all services
    await runner.run_all()


if __name__ == "__main__":
    asyncio.run(main())
