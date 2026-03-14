"""
Clarity+ Jetson Voice Service
=============================
Runs VoiceListener (mic, Vosk, TTS) on Jetson. POSTs to Pi for /voice/intent and /api/voice/status.
Exposes /trigger for Pi to forward space-bar / test trigger.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger("service.voice")

# Load config from jetson root; ensure voice service dir is on path
import sys
from pathlib import Path
_jet_root = Path(__file__).resolve().parent.parent.parent
_voice_dir = Path(__file__).resolve().parent
for p in (str(_jet_root), str(_voice_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

from config import settings

_listener = None


@asynccontextmanager
async def lifespan(app):
    global _listener
    backend_url = f"http://{settings.RPI_IP}:8000" if settings.RPI_IP else None
    if not backend_url:
        logger.warning("RPI_IP not set — voice service will not start")
        yield
        return
    from voice_listener import JetsonVoiceListener
    _listener = JetsonVoiceListener(backend_url=backend_url)
    _listener.start()
    yield
    if _listener:
        _listener.stop()
    _listener = None


app = FastAPI(title="Clarity+ Voice Service (Jetson)", lifespan=lifespan)


@app.post("/trigger")
def trigger_listen():
    """Skip wake word and start listening (e.g. space bar trigger from Pi)."""
    if _listener:
        _listener.trigger_listen()
        return {"status": "ok", "message": "Listening"}
    return {"status": "error", "message": "Voice listener not running"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "voice"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
