"""
Clarity+ Eye Strain Service
===========================
FastAPI microservice: EAR, sclera redness, puffiness, blink rate.
Mode 1: /analyze (single image)
Mode 2: /analyze/stream (video stream)
Runs on port 8005.
"""

import sys
import time
import uuid
import logging
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Clarity+ Eye Strain Service")
logger = logging.getLogger("service.eyes")

# Load analyzer at startup (mock in pytest)
_analyzer = None
_stream_sessions: dict[str, "BlinkTracker"] = {}


def _load_analyzer():
    global _analyzer
    if "pytest" in sys.modules:
        from unittest.mock import MagicMock

        _analyzer = MagicMock()
        _analyzer.analyze_frame = MagicMock(
            return_value={
                "ear": 0.28,
                "eye_openness": "Partial",
                "sclera_redness": 1.8,
                "puffiness": "Moderate",
                "blink_rate": None,
                "drowsiness": "Mild",
                "score": 74,
            }
        )
        return
    from inference import EyeStrainAnalyzer

    # Use False so one instance works for both image and stream
    _analyzer = EyeStrainAnalyzer(static_image_mode=False)


_load_analyzer()

# Import after analyzer load (blink_tracker has no MediaPipe dep)
from blink_tracker import BlinkTracker
from inference import (
    _blink_rate_status,
    _classify_drowsiness,
    _classify_eye_openness,
    compute_eye_score,
)


class AnalysisRequest(BaseModel):
    image_path: str


class StreamRequest(BaseModel):
    stream_url: str | None = None
    device_id: int = 0
    session_id: str | None = None
    max_frames: int = 300
    process_every_nth: int = 1


@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    """Single image mode: EAR, sclera redness, puffiness. blink_rate=null."""
    logger.info(f"Analyzing eyes for: {request.image_path}")

    path = Path(request.image_path)
    if not path.exists():
        return {"service": "eyes", "error": "image_not_found", "score": None}

    frame = cv2.imread(str(path))
    if frame is None:
        return {"service": "eyes", "error": "invalid_image", "score": None}

    result = _analyzer.analyze_frame(frame, blink_rate=None)
    if result is None:
        return {"service": "eyes", "error": "no_face_detected", "score": None}

    details = {
        "ear": result["ear"],
        "eye_openness": result["eye_openness"],
        "sclera_redness": result["sclera_redness"],
        "puffiness": result["puffiness"],
        "blink_rate": None,
        "drowsiness": result["drowsiness"],
        "note": "Blink rate unavailable in image mode — use stream endpoint for full analysis",
    }

    return {
        "service": "eyes",
        "mode": "image",
        "score": result["score"],
        "details": details,
    }


@app.post("/analyze/stream")
async def analyze_stream(request: StreamRequest = None):
    """Video stream mode: all metrics including blink_rate."""
    req = request or StreamRequest()
    source = req.stream_url if req.stream_url else req.device_id
    session_id = req.session_id or str(uuid.uuid4())
    max_frames = max(1, min(req.max_frames, 600))
    process_every = max(1, req.process_every_nth)

    if session_id not in _stream_sessions:
        _stream_sessions[session_id] = BlinkTracker()
    tracker = _stream_sessions[session_id]

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        return {
            "service": "eyes",
            "mode": "stream",
            "error": "camera_unavailable",
            "score": None,
        }

    start_time = time.time()
    ear_list: list[float] = []
    redness_list: list[float] = []
    puffiness_list: list[str] = []
    frames_processed = 0
    frame_idx = 0

    try:
        while frames_processed < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % process_every != 0:
                frame_idx += 1
                continue
            frame_idx += 1

            ts = time.time()
            result = _analyzer.analyze_frame(frame, blink_rate=None)
            if result is not None:
                ear_list.append(result["ear"])
                redness_list.append(result["sclera_redness"])
                puffiness_list.append(result["puffiness"])
                tracker.update(result["ear"], ts)
                frames_processed += 1

            if frames_processed >= max_frames:
                break
    finally:
        cap.release()

    duration = time.time() - start_time
    blink_rate = tracker.blinks_per_minute()
    blink_status = _blink_rate_status(blink_rate)

    if not ear_list:
        return {
            "service": "eyes",
            "mode": "stream",
            "error": "no_face_detected",
            "frames_analyzed": 0,
            "duration_seconds": round(duration, 2),
            "score": None,
        }

    ear_med = float(np.median(ear_list))
    redness_mean = float(np.mean(redness_list))
    puff_mode = max(set(puffiness_list), key=puffiness_list.count)
    score = compute_eye_score(ear_med, redness_mean, puff_mode, blink_rate)
    drowsiness = _classify_drowsiness(ear_med, blink_rate)

    details = {
        "ear": round(ear_med, 4),
        "eye_openness": _classify_eye_openness(ear_med),
        "sclera_redness": round(redness_mean, 2),
        "puffiness": puff_mode,
        "blink_rate": blink_rate,
        "blink_rate_status": blink_status,
        "drowsiness": drowsiness,
        "frames_analyzed": frames_processed,
        "duration_seconds": round(duration, 2),
    }

    return {
        "service": "eyes",
        "mode": "stream",
        "score": score,
        "details": details,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8005)
