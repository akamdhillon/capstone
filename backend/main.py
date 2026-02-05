# =============================================================================
# CLARITY+ BACKEND - FASTAPI APPLICATION
# =============================================================================
"""
Main FastAPI application for the Clarity+ Smart Mirror API Gateway.
Runs on Raspberry Pi 4, orchestrating ML inference requests to Jetson.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from database.connection import init_database, close_database
from routes import analysis, users
from tasks.janitor import start_scheduler, shutdown_scheduler

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup/shutdown events for database and scheduler.
    """
    logger.info("🚀 Starting Clarity+ Backend Orchestrator...")
    
    # Initialize database
    await init_database()
    logger.info("✓ Database initialized")
    
    # Start background scheduler for Janitor task
    start_scheduler()
    logger.info("✓ Background scheduler started")
    
    logger.info(f"✓ Thermal hardware: {'ENABLED' if settings.thermal_enabled else 'DISABLED'}")
    logger.info(f"✓ Scoring weights: {settings.weights}")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Clarity+ Backend...")
    shutdown_scheduler()
    await close_database()
    logger.info("✓ Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Clarity+ API Gateway",
    description="Backend orchestrator for the Clarity+ Smart Mirror wellness system",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://192.168.10.1:3000",
        f"http://{settings.rpi_ip}:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(users.router, prefix="/api", tags=["Users"])


@app.get("/health")
async def health_check():
    """
    Health check endpoint for container orchestration.
    Returns service status and configuration info.
    """
    return {
        "status": "ok",
        "service": "clarity-backend",
        "thermal_enabled": settings.thermal_enabled,
        "weights": settings.weights
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Clarity+ Smart Mirror API",
        "docs": "/docs",
        "health": "/health"
    }
