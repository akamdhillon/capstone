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
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import settings
from routes import analysis, face
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

# --- SSE Debug Events ---
from debug_events import emit_debug_event, get_sse_listeners, frame_poller_context

JETSON_CAPTURE_URL = f"http://{settings.JETSON_IP}:8001/capture-frame"

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


async def _check_ollama():
    """Verify Ollama is reachable. Use longer timeout for Pi→Jetson network."""
    import httpx
    url = f"{settings.OLLAMA_HOST.rstrip('/')}/api/tags"
    timeout = getattr(settings, "OLLAMA_CHECK_TIMEOUT", 8.0)
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    logger.info("Ollama is reachable at %s. LLM voice intents will work.", settings.OLLAMA_HOST)
                    return True
        except Exception as e:
            if attempt == 0:
                continue
            logger.info(
                "Ollama not reachable at %s — voice intents will use fallback responses. "
                "To enable LLM: run 'ollama serve' on the Jetson, ensure %s is correct, and network allows port 11434. (%s)",
                settings.OLLAMA_HOST, "OLLAMA_HOST", str(e)[:80],
            )
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Voice (mic, Vosk, TTS) runs on Jetson; Pi keeps /voice/intent and /api/voice/status.
    """
    logger.info("Starting Clarity+ Backend...")
    logger.info(f"Thermal hardware: {'ENABLED' if settings.THERMAL_ENABLED else 'DISABLED'}")
    logger.info(f"Scoring weights: {settings.weights}")

    await _check_ollama()

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
        "http://localhost:5173",
        f"http://{settings.RPI_IP}:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(face.router, prefix="/api", tags=["Face"])
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
    """Endpoint for Jetson voice service to report state; broadcasts to frontend via WebSocket."""
    logger.info(f"Voice Status Update: {status.state}")
    await manager.broadcast(status.model_dump())
    return {"status": "ok"}


@app.post("/api/voice/trigger")
async def trigger_voice_listen():
    """Forward to Jetson voice service (skip wake word, start listening)."""
    import httpx
    url = f"http://{settings.JETSON_IP}:{getattr(settings, 'JETSON_VOICE_PORT', 8007)}/trigger"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(url)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.warning("Voice trigger forward failed: %s", e)
        return {"status": "error", "message": f"Jetson voice service unreachable: {e}"}


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


class BroadcastPayload(BaseModel):
    navigate: Optional[str] = None
    action: Optional[str] = None
    result: Optional[dict] = None
    display_name: Optional[str] = None
    user_id: Optional[str] = None
    captured_image: Optional[str] = None
    scores: Optional[dict] = None
    overall_score: Optional[float] = None
    enrollment_start: Optional[bool] = None
    enrollment_step: Optional[int] = None
    enrollment_result: Optional[dict] = None
    debug_progress: Optional[dict] = None
    debug_frame: Optional[str] = None
    debug_camera_url: Optional[str] = None


@app.get("/api/debug/sse")
async def debug_sse_stream():
    """Server-Sent Events stream for debug progress and frames."""
    _listeners = get_sse_listeners()
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=32)
    _listeners.add(queue)

    async def event_gen():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _listeners.discard(queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/action")
async def broadcast_action(command: ActionCommand):
    """Broadcast a specific action trigger to the frontend via WebSocket."""
    logger.info(f"Action Command: {command.action}")
    await manager.broadcast({"action": command.action})
    return {"status": "ok", "action": command.action}


@app.post("/api/broadcast")
async def broadcast(payload: BroadcastPayload):
    """Broadcast a message to all WebSocket clients (e.g. navigate + result)."""
    msg = payload.model_dump(exclude_none=True)
    if msg:
        await manager.broadcast(msg)
        if "debug_progress" in msg:
            await emit_debug_event({"type": "progress", **msg["debug_progress"]})
        if "debug_frame" in msg:
            await emit_debug_event({"type": "frame", "image": msg["debug_frame"]})
    return {"status": "ok"}


# --- Results Storage ---
_DATA_DIR = Path(__file__).resolve().parent / "data"
POSTURE_RESULTS_FILE = _DATA_DIR / "posture_results.json"
EYE_RESULTS_FILE = _DATA_DIR / "eye_results.json"
THERMAL_RESULTS_FILE = _DATA_DIR / "thermal_results.json"
SKIN_RESULTS_FILE = _DATA_DIR / "skin_results.json"

class PostureResultData(BaseModel):
    score: int
    status: str
    neck_angle: float
    torso_angle: float
    neck_status: str
    torso_status: str
    recommendations: List[str] = []
    frames_analyzed: int = 0
    user_id: Optional[str] = None

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
async def get_posture_results(user_id: Optional[str] = None):
    """Get posture assessment history, optionally filtered by user_id."""
    if not POSTURE_RESULTS_FILE.exists():
        return []
    try:
        history = json.loads(POSTURE_RESULTS_FILE.read_text())
        if user_id:
            history = [e for e in history if e.get("user_id") == user_id]
        return history
    except Exception:
        return []


class PostureRunRequest(BaseModel):
    user_id: Optional[str] = None

@app.post("/api/posture/run")
async def run_posture(req: PostureRunRequest = None):
    """Trigger posture analysis using Jetson camera (no image from frontend)."""
    import httpx
    user_id = (req.user_id if req else None) or "unknown"
    await emit_debug_event({"type": "progress", "phase": "running", "service": "posture", "message": "Running posture analysis (5s capture)..."})
    url = f"http://{settings.JETSON_IP}:{settings.JETSON_POSTURE_PORT}/posture/run"
    try:
        async with frame_poller_context(JETSON_CAPTURE_URL):
            async with httpx.AsyncClient(timeout=35.0) as client:
                response = await client.post(url, json={"user_id": user_id})
                response.raise_for_status()
                data = response.json()
        # Save result for history
        if "error" not in data:
            neck = data.get("neck") or {}
            torso = data.get("torso") or {}
            entry = PostureResultData(
                score=data.get("score", 0),
                status=data.get("status", "unknown"),
                neck_angle=neck.get("angle", 0) if isinstance(neck, dict) else 0,
                torso_angle=torso.get("angle", 0) if isinstance(torso, dict) else 0,
                neck_status=neck.get("status", "unknown") if isinstance(neck, dict) else "unknown",
                torso_status=torso.get("status", "unknown") if isinstance(torso, dict) else "unknown",
                recommendations=data.get("recommendations", []),
                frames_analyzed=data.get("frames_analyzed", 0),
                user_id=user_id,
            )
            await save_posture_result(entry)
        return data
    except Exception as e:
        logger.error(f"Posture run failed: {e}")
        return {"service": "posture", "error": str(e), "score": 0}


def _load_json_file(path: Path, default: list) -> list:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_json_file(path: Path, data: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


class EyeResultData(BaseModel):
    score: float
    details: Optional[dict] = None
    user_id: Optional[str] = None


class ThermalResultData(BaseModel):
    score: float
    details: Optional[dict] = None
    user_id: Optional[str] = None


class SkinResultData(BaseModel):
    score: Optional[float] = None
    details: Optional[dict] = None
    user_id: Optional[str] = None
    recommendation: Optional[str] = None
    status: Optional[str] = None


@app.post("/api/eyes/results")
async def save_eye_result(result: EyeResultData):
    """Save an eye strain assessment result."""
    import datetime
    history = _load_json_file(EYE_RESULTS_FILE, [])
    entry = result.model_dump()
    entry["timestamp"] = datetime.datetime.now().isoformat()
    history.append(entry)
    if len(history) > 100:
        history = history[-100:]
    _save_json_file(EYE_RESULTS_FILE, history)
    return {"status": "ok", "total_results": len(history)}


@app.get("/api/eyes/results")
async def get_eye_results(user_id: Optional[str] = None):
    history = _load_json_file(EYE_RESULTS_FILE, [])
    if user_id:
        history = [e for e in history if e.get("user_id") == user_id]
    return history


@app.post("/api/thermal/results")
async def save_thermal_result(result: ThermalResultData):
    """Save a thermal scan result."""
    import datetime
    history = _load_json_file(THERMAL_RESULTS_FILE, [])
    entry = result.model_dump()
    entry["timestamp"] = datetime.datetime.now().isoformat()
    history.append(entry)
    if len(history) > 100:
        history = history[-100:]
    _save_json_file(THERMAL_RESULTS_FILE, history)
    return {"status": "ok", "total_results": len(history)}


@app.get("/api/thermal/results")
async def get_thermal_results(user_id: Optional[str] = None):
    history = _load_json_file(THERMAL_RESULTS_FILE, [])
    if user_id:
        history = [e for e in history if e.get("user_id") == user_id]
    return history


@app.post("/api/skin/results")
async def save_skin_result(result: SkinResultData):
    """Save a skin analysis result."""
    import datetime
    history = _load_json_file(SKIN_RESULTS_FILE, [])
    entry = result.model_dump(exclude_none=True)
    entry["timestamp"] = datetime.datetime.now().isoformat()
    history.append(entry)
    if len(history) > 100:
        history = history[-100:]
    _save_json_file(SKIN_RESULTS_FILE, history)
    return {"status": "ok", "total_results": len(history)}


@app.get("/api/skin/results")
async def get_skin_results(user_id: Optional[str] = None):
    history = _load_json_file(SKIN_RESULTS_FILE, [])
    if user_id:
        history = [e for e in history if e.get("user_id") == user_id]
    return history


class SkinRunRequest(BaseModel):
    user_id: Optional[str] = None


@app.post("/api/skin/run")
async def run_skin(req: SkinRunRequest = None):
    """Trigger skin analysis via Jetson orchestrator; save result and return."""
    import httpx
    user_id = (req.user_id if req else None) or "unknown"
    await emit_debug_event({"type": "progress", "phase": "running", "service": "skin", "message": "Running skin analysis..."})
    url = f"http://{settings.JETSON_IP}:8001/skin/run"
    try:
        async with frame_poller_context(JETSON_CAPTURE_URL):
            async with httpx.AsyncClient(timeout=35.0) as client:
                payload = {} if not req else {"user_id": user_id}
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        if "error" not in data and data.get("score") is not None:
            entry = SkinResultData(
                score=float(data.get("score", 0)),
                details=data.get("details"),
                user_id=user_id,
                recommendation=data.get("recommendation"),
                status=data.get("status"),
            )
            await save_skin_result(entry)
        return data
    except Exception as e:
        logger.error(f"Skin run failed: {e}")
        return {"service": "skin", "error": str(e), "score": 0}


@app.get("/api/summary")
async def get_daily_summary(user_id: Optional[str] = None):
    """Return a daily wellness summary aggregated from posture, eye, thermal, and skin results."""
    history = _load_json_file(POSTURE_RESULTS_FILE, [])
    if user_id:
        history = [e for e in history if e.get("user_id") == user_id]

    eye_history = _load_json_file(EYE_RESULTS_FILE, [])
    if user_id:
        eye_history = [e for e in eye_history if e.get("user_id") == user_id]

    thermal_history = _load_json_file(THERMAL_RESULTS_FILE, [])
    if user_id:
        thermal_history = [e for e in thermal_history if e.get("user_id") == user_id]

    skin_history = _load_json_file(SKIN_RESULTS_FILE, [])
    if user_id:
        skin_history = [e for e in skin_history if e.get("user_id") == user_id]

    latest_eye = eye_history[-1] if eye_history else None
    latest_thermal = thermal_history[-1] if thermal_history else None
    latest_skin = skin_history[-1] if skin_history else None

    if not history:
        return {
            "total_assessments": 0,
            "average_score": None,
            "latest": None,
            "trend": "no_data",
            "latest_eye": latest_eye,
            "latest_thermal": latest_thermal,
            "latest_skin": latest_skin,
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
        "latest_eye": latest_eye,
        "latest_thermal": latest_thermal,
        "latest_skin": latest_skin,
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
