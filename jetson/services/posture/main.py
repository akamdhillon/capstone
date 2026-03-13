"""
Clarity+ Posture Service
========================
Real-time posture analysis using MediaPipe Pose.
Captures frames from camera, calculates neck/torso angles,
and returns structured posture assessment results.

Runs on Jetson Nano (port 8004) or Mac (CPU) for testing.
"""

import os
import sys
import time
import math
import logging
import urllib.request
from pathlib import Path

# Add jetson root to path for config import
_jet_root = Path(__file__).resolve().parent.parent.parent
if str(_jet_root) not in sys.path:
    sys.path.insert(0, str(_jet_root))
from dataclasses import dataclass, asdict
from collections import deque
from typing import Optional

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from fastapi import FastAPI
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("service.posture")

# ---------------------------------------------------------------------------
# Pose Landmark indices (same as legacy MediaPipe Pose)
# ---------------------------------------------------------------------------
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_EAR = 7
RIGHT_EAR = 8
LEFT_HIP = 23
RIGHT_HIP = 24

# ---------------------------------------------------------------------------
# Model path
# ---------------------------------------------------------------------------
_SERVICE_DIR = Path(__file__).parent.resolve()
_MODEL_PATH = _SERVICE_DIR / "pose_landmarker_lite.task"
_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"


def _ensure_model():
    """Download pose landmarker model if not present."""
    if _MODEL_PATH.exists():
        return str(_MODEL_PATH)
    logger.info(f"Downloading pose landmarker model to {_MODEL_PATH}...")
    urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
    logger.info("Model downloaded.")
    return str(_MODEL_PATH)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Clarity+ Posture Service")


# ---------------------------------------------------------------------------
# Calibrated Configuration
# ---------------------------------------------------------------------------
class PostureConfig:
    """
    Calibrated thresholds for side-view posture analysis.
    - Neck: ear-to-shoulder angle from vertical
    - Torso: shoulder-to-hip angle from vertical
    """
    NECK_GOOD = 8.0
    NECK_MODERATE = 12.0
    NECK_POOR = 18.0

    TORSO_GOOD = 5.0
    TORSO_MODERATE = 8.0
    TORSO_POOR = 12.0

    COMBINED_GOOD_NECK = 8.0
    COMBINED_GOOD_TORSO = 5.0

    SMOOTHING_WINDOW = 10
    CAPTURE_DURATION = 5  # seconds (shortened for voice UX)
    ALIGNMENT_THRESHOLD_PERCENT = 0.15


config = PostureConfig()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class AnalysisRequest(BaseModel):
    image_path: str = ""  # Legacy compat (orchestrator sends this)
    user_id: str = "unknown"


class RunPostureRequest(BaseModel):
    user_id: str = "unknown"


# ---------------------------------------------------------------------------
# MediaPipe Tasks Setup (loaded once)
# ---------------------------------------------------------------------------
pose_landmarker: Optional[vision.PoseLandmarker] = None


@app.on_event("startup")
def load_models():
    global pose_landmarker
    logger.info("Loading MediaPipe Pose Landmarker (Tasks API)...")
    t0 = time.time()
    model_path = _ensure_model()
    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
    )
    pose_landmarker = vision.PoseLandmarker.create_from_options(options)
    logger.info(f"Pose landmarker loaded in {time.time() - t0:.1f}s")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "posture", "model_loaded": pose_landmarker is not None}


# ---------------------------------------------------------------------------
# Core Posture Analysis Functions
# ---------------------------------------------------------------------------
def calculate_angle(x1, y1, x2, y2):
    """Calculate angle from vertical (degrees). Measures forward lean."""
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    if dy < 1e-6:
        return 0.0
    return np.degrees(np.arctan(dx / dy))


def find_distance(x1, y1, x2, y2):
    """Euclidean distance between two points."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def assess_status(angle, good_thresh, mod_thresh):
    """Classify angle into good/moderate/poor."""
    if angle < good_thresh:
        return "good"
    elif angle < mod_thresh:
        return "moderate"
    else:
        return "poor"


def analyze_frame_from_landmarks(landmarks, w, h):
    """
    Analyze a single frame's pose landmarks (list of NormalizedLandmark).
    Returns (neck_angle, torso_angle) or None if landmarks insufficient.
    """
    if len(landmarks) < 24:
        return None
    lm = landmarks
    l_shldr_x = lm[LEFT_SHOULDER].x * w
    l_shldr_y = lm[LEFT_SHOULDER].y * h
    l_ear_x = lm[LEFT_EAR].x * w
    l_ear_y = lm[LEFT_EAR].y * h
    l_hip_x = lm[LEFT_HIP].x * w
    l_hip_y = lm[LEFT_HIP].y * h

    neck_angle = calculate_angle(l_shldr_x, l_shldr_y, l_ear_x, l_ear_y)
    torso_angle = calculate_angle(l_hip_x, l_hip_y, l_shldr_x, l_shldr_y)

    return neck_angle, torso_angle


def _detect_pose(landmarker, rgb_image):
    """Run pose detection on an RGB numpy array. Returns pose_landmarks or None."""
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
    result = landmarker.detect(mp_image)
    if result.pose_landmarks and len(result.pose_landmarks) > 0:
        return result.pose_landmarks[0]
    return None


def run_posture_analysis(duration_sec: int = 5) -> dict:
    """
    Run a timed posture analysis session using the camera.
    Captures frames for `duration_sec`, analyzes each, returns aggregated result.
    """
    if pose_landmarker is None:
        return {"service": "posture", "error": "Model not loaded", "score": 0}

    from config import settings
    cam_device = getattr(settings, "CAMERA_DEVICE_PRIMARY", 0)
    cap = cv2.VideoCapture(cam_device)
    if not cap.isOpened():
        logger.error("Camera not available")
        return {"service": "posture", "error": "Camera not available", "score": 0}

    neck_angles = deque(maxlen=config.SMOOTHING_WINDOW * 10)
    torso_angles = deque(maxlen=config.SMOOTHING_WINDOW * 10)
    frame_count = 0
    start = time.time()

    logger.info(f"Starting {duration_sec}s posture capture...")

    try:
        while (time.time() - start) < duration_sec:
            ret, frame = cap.read()
            if not ret:
                continue

            h, w, _ = frame.shape
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            landmarks = _detect_pose(pose_landmarker, rgb)

            if landmarks:
                angles = analyze_frame_from_landmarks(landmarks, w, h)
                if angles:
                    neck_angles.append(angles[0])
                    torso_angles.append(angles[1])
                    frame_count += 1
    finally:
        cap.release()

    elapsed = time.time() - start
    logger.info(f"Captured {frame_count} frames in {elapsed:.1f}s")

    if frame_count < 3:
        return {
            "service": "posture",
            "error": "Not enough frames with visible pose",
            "score": 0,
            "frames_analyzed": frame_count,
        }

    # Aggregate results
    neck_median = float(np.median(list(neck_angles)))
    torso_median = float(np.median(list(torso_angles)))

    neck_status = assess_status(neck_median, config.NECK_GOOD, config.NECK_MODERATE)
    torso_status = assess_status(torso_median, config.TORSO_GOOD, config.TORSO_MODERATE)

    # Build recommendations
    recommendations = []
    if neck_status in ("moderate", "poor"):
        recommendations.append("Forward head detected - practice chin tucks")
        recommendations.append("Check screen height (should be at eye level)")
    if torso_status in ("moderate", "poor"):
        recommendations.append("Slouching detected - sit or stand more upright")
        recommendations.append("Engage core muscles and retract shoulder blades")

    # Overall status (BOTH must be good)
    if neck_median < config.COMBINED_GOOD_NECK and torso_median < config.COMBINED_GOOD_TORSO:
        overall = "good"
        score = 90 + int(min(10, (config.COMBINED_GOOD_NECK - neck_median) * 2))
        message = "Excellent posture! Keep it up."
    elif neck_status == "poor" or torso_status == "poor":
        overall = "poor"
        score = max(20, 50 - int(max(neck_median - config.NECK_MODERATE, torso_median - config.TORSO_MODERATE) * 2))
        message = "Poor posture detected. Please correct your alignment."
    else:
        overall = "moderate"
        score = 60 + int(min(20, (config.NECK_MODERATE - neck_median) + (config.TORSO_MODERATE - torso_median)))
        message = "Moderate posture. Small corrections would help."

    score = max(0, min(100, score))

    return {
        "service": "posture",
        "score": score,
        "status": overall,
        "message": message,
        "neck": {
            "angle": round(neck_median, 1),
            "status": neck_status,
        },
        "torso": {
            "angle": round(torso_median, 1),
            "status": torso_status,
        },
        "recommendations": recommendations,
        "frames_analyzed": frame_count,
        "duration_seconds": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/posture/run")
async def run_posture(request: RunPostureRequest):
    """Voice-triggered posture check. Captures from camera and analyzes."""
    logger.info(f"Posture check requested for user: {request.user_id}")
    result = run_posture_analysis(duration_sec=config.CAPTURE_DURATION)
    return result


@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    """Legacy endpoint for orchestrator compatibility."""
    logger.info(f"Analyze posture for: {request.image_path or 'camera'}")

    if pose_landmarker is None:
        return {"service": "posture", "score": 0, "details": {"error": "Model not loaded"}}

    # If an image_path is provided, analyze that single frame
    if request.image_path and os.path.exists(request.image_path):
        img = cv2.imread(request.image_path)
        if img is not None:
            h, w, _ = img.shape
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            landmarks = _detect_pose(pose_landmarker, rgb)

            if landmarks:
                angles = analyze_frame_from_landmarks(landmarks, w, h)
                if angles:
                    neck_status = assess_status(angles[0], config.NECK_GOOD, config.NECK_MODERATE)
                    torso_status = assess_status(angles[1], config.TORSO_GOOD, config.TORSO_MODERATE)

                    if neck_status == "good" and torso_status == "good":
                        score = 90
                    elif neck_status == "poor" or torso_status == "poor":
                        score = 40
                    else:
                        score = 65

                    return {
                        "service": "posture",
                        "score": score,
                        "details": {
                            "neck_angle": round(angles[0], 1),
                            "torso_angle": round(angles[1], 1),
                            "neck_status": neck_status,
                            "torso_status": torso_status,
                        }
                    }

        return {"service": "posture", "score": 50, "details": {"error": "Could not analyze image"}}

    # Fallback: run a live camera analysis
    result = run_posture_analysis(duration_sec=config.CAPTURE_DURATION)
    return result


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
