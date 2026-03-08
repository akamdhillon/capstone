# =============================================================================
# CLARITY+ BACKEND - FASTAPI APPLICATION
# =============================================================================
"""
Main FastAPI application for the Clarity+ Smart Mirror API Gateway.
Runs on Raspberry Pi 4, orchestrating ML inference requests to Jetson.
"""

import asyncio
import logging
import json
from contextlib import asynccontextmanager
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from routes import analysis, face, llm_voice
import voice_orchestrator
from voice_listener import VoiceListener

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
_voice_listener: VoiceListener | None = None

# --- Models ---
class VoiceStatus(BaseModel):
    state: str  # IDLE, LISTENING, PROCESSING, SPEAKING
    user_id: Optional[str] = None
    display_name: Optional[str] = None
    caption: Optional[str] = None

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Starts the voice listener background thread on startup.
    """
    global _voice_listener
    logger.info("Starting Clarity+ Backend...")
    
    logger.info(f"Thermal hardware: {'ENABLED' if settings.THERMAL_ENABLED else 'DISABLED'}")
    logger.info(f"Scoring weights: {settings.weights}")

    # Start voice listener (mic -> Vosk -> orchestrator -> TTS)
    loop = asyncio.get_running_loop()
    _voice_listener = VoiceListener(ws_manager=manager, event_loop=loop)
    _voice_listener.start()
    
    yield
    
    # Shutdown
    if _voice_listener:
        _voice_listener.stop()
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
    await manager.broadcast(status.model_dump())
    return {"status": "ok"}


# --- Navigation Endpoint ---

class NavigateCommand(BaseModel):
    view: str  # 'idle', 'posture', 'analysis', 'enrollment'

@app.post("/api/navigate")
async def navigate(command: NavigateCommand):
    """Broadcast a navigation command to the frontend via WebSocket."""
    logger.info(f"Navigation Command: {command.view}")
    await manager.broadcast({"navigate": command.view})
    return {"status": "ok", "navigated_to": command.view}


class ActionCommand(BaseModel):
    action: str  # e.g., 'recognize'

@app.post("/api/action")
async def broadcast_action(command: ActionCommand):
    """Broadcast a specific action trigger to the frontend via WebSocket."""
    logger.info(f"Action Command: {command.action}")
    await manager.broadcast({"action": command.action})
    return {"status": "ok", "action": command.action}


# --- Posture Results Storage ---

POSTURE_RESULTS_FILE = Path(__file__).resolve().parent / "data" / "posture_results.json"

class PostureResultData(BaseModel):
    score: int
    status: str
    neck_angle: float
    torso_angle: float
    neck_status: str
    torso_status: str
    recommendations: List[str] = []
    frames_analyzed: int = 0

@app.post("/api/posture/results")
async def save_posture_result(result: PostureResultData):
    """Save a posture assessment result."""
    import datetime
    POSTURE_RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    history = []
    if POSTURE_RESULTS_FILE.exists():
        try:
            history = json.loads(POSTURE_RESULTS_FILE.read_text())
        except Exception:
            history = []

    entry = result.model_dump()
    entry["timestamp"] = datetime.datetime.now().isoformat()
    history.append(entry)

    # Keep last 100 results
    if len(history) > 100:
        history = history[-100:]

    POSTURE_RESULTS_FILE.write_text(json.dumps(history, indent=2))
    logger.info(f"Posture result saved: score={result.score}, status={result.status}")
    return {"status": "ok", "total_results": len(history)}

@app.get("/api/posture/results")
async def get_posture_results():
    """Get posture assessment history."""
    if POSTURE_RESULTS_FILE.exists():
        try:
            return json.loads(POSTURE_RESULTS_FILE.read_text())
        except Exception:
            return []
    return []


@app.get("/api/summary")
async def get_daily_summary(user_id: Optional[str] = None):
    """Return a daily wellness summary aggregated from posture results."""
    history = []
    if POSTURE_RESULTS_FILE.exists():
        try:
            history = json.loads(POSTURE_RESULTS_FILE.read_text())
        except Exception:
            history = []

    if not history:
        return {
            "total_assessments": 0,
            "average_score": None,
            "latest": None,
            "trend": "no_data",
        }

    scores = [entry["score"] for entry in history if "score" in entry]
    latest = history[-1]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    trend = "stable"
    if len(scores) >= 2:
        recent = scores[-3:]
        if recent[-1] > recent[0]:
            trend = "improving"
        elif recent[-1] < recent[0]:
            trend = "declining"

    return {
        "total_assessments": len(history),
        "average_score": avg_score,
        "latest": latest,
        "trend": trend,
    }


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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
