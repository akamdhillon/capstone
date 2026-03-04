# =============================================================================
# CLARITY+ BACKEND - FASTAPI APPLICATION
# =============================================================================
"""
Main FastAPI application for the Clarity+ Smart Mirror API Gateway.
Runs on Raspberry Pi 4, orchestrating ML inference requests to Jetson.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from routes import analysis, face, llm_voice
import voice_orchestrator

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# --- Models ---
class VoiceStatus(BaseModel):
    state: str  # IDLE, LISTENING, PROCESSING, SPEAKING
    user_id: Optional[str] = None
    display_name: Optional[str] = None

# Configure logging
# settings = get_settings() # Removed, imported directly
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Stateless backend - no DB or Scheduler init.
    """
    logger.info("🚀 Starting Clarity+ Backend...")
    
    logger.info(f"✓ Thermal hardware: {'ENABLED' if settings.THERMAL_ENABLED else 'DISABLED'}")
    logger.info(f"✓ Scoring weights: {settings.weights}")
    
    yield
    
    logger.info("Shutting down Clarity+ Backend...")


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
        f"http://{settings.RPI_IP}:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(face.router, prefix="/api", tags=["Face"])
app.include_router(llm_voice.router, prefix="/api/voice_old", tags=["Voice Old"])
app.include_router(voice_orchestrator.router, prefix="/voice", tags=["Voice"])


# --- Voice System Endpoints ---

@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """WebSocket for frontend to receive voice state updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/voice/status")
async def update_voice_status(status: VoiceStatus):
    """Endpoint for Pi Client to report its current state."""
    logger.info(f"Voice Status Update: {status.state}")
    await manager.broadcast(status.dict())
    return {"status": "ok"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "clarity-backend",
        "thermal_enabled": settings.THERMAL_ENABLED
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Clarity+ Smart Mirror API",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    # Run the server with default host 0.0.0.0 to allow external access
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
