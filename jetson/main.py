"""
Clarity+ Orchestrator
=====================
Command Center.
Starts camera, saves snapshots, and orchestrates analysis via microservices.
"""

import sys
import os
import time
import uuid
import logging
import cv2
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
import requests
import uvicorn

from typing import Optional
import base64
import numpy as np
from pydantic import BaseModel

# --- Camera Manager ---
from config import settings, IS_MAC

logger_cam = logging.getLogger("camera")

class CameraManager:
    """
    Manages camera capture (Embedded).
    """
    
    def __init__(self):
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        self.width = settings.CAMERA_RESOLUTION_WIDTH
        self.height = settings.CAMERA_RESOLUTION_HEIGHT
        self.fps = settings.CAMERA_FPS
        
    def start(self) -> bool:
        """Start the camera."""
        if self._running:
            return True
            
        source = 0
        if IS_MAC:
            source = settings.MAC_CAMERA_INDEX
        else:
            source = settings.CAMERA_DEVICE_PRIMARY
            
        logger_cam.info(f"Opening camera source: {source}")
        self._cap = cv2.VideoCapture(source)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        
        if not self._cap.isOpened():
            logger_cam.error("Failed to open camera. Entering LOCKDOWN/MOCK mode.")
            # We don't return False here, we start a mock thread instead to keep the app alive
            self._running = True
            self._thread = threading.Thread(target=self._mock_capture_loop, daemon=True)
            self._thread.start()
            return True
            
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        return True

    def _mock_capture_loop(self):
        """Generates dummy frames when camera is unavailable."""
        logger_cam.warning("Starting MOCK camera loop (Green screen).")
        while self._running:
             # Create a green image with timestamp
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            frame[:] = (0, 255, 0) # Green
            
            # Add text
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, f"MOCK CAMERA - {timestamp}", (50, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            
            with self._lock:
                self._frame = frame
                
            time.sleep(1.0 / self.fps)

        
    def _capture_loop(self):
        while self._running:
            if self._cap:
                ret, frame = self._cap.read()
                if ret:
                    with self._lock:
                        self._frame = frame
                else:
                    logger_cam.warning("Failed to read frame")
                    time.sleep(0.1)
            time.sleep(1.0 / self.fps)
            
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        if self._cap:
            self._cap.release()
            
    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._frame is not None:
                return self._frame.copy()
        return None

camera = CameraManager()


# Configuration
SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# Service Ports
SERVICES = {
    "face": 8002,
    "skin": 8003,
    "posture": 8004,
    "eyes": 8005,
    "thermal": 8006
}

logger = logging.getLogger("orchestrator")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app):
    logger.info("Starting Camera...")
    if camera.start():
        logger.info("Camera started.")
    else:
        logger.error("Failed to start camera.")
    yield
    logger.info("Stopping Camera...")
    camera.stop()


app = FastAPI(title="Clarity+ Orchestrator", lifespan=lifespan)

class AnalyzePayload(BaseModel):
    image: Optional[str] = None  # base64-encoded JPEG from frontend


@app.post("/analyze")
async def analyze_endpoint(payload: AnalyzePayload = None):
    """
    Main entry point for analysis.
    Accepts an optional base64 image from the frontend/backend.
    Falls back to local camera capture if no image provided.
    """
    logger.info("Received analyze request")

    timestamp = int(time.time())
    filename = f"snapshot_{timestamp}.jpg"
    filepath = os.path.join(SNAPSHOT_DIR, filename)

    # 1. Acquire image - prefer base64 payload, fall back to camera
    if payload and payload.image:
        try:
            img_bytes = base64.b64decode(payload.image)
            with open(filepath, "wb") as f:
                f.write(img_bytes)
            logger.info(f"Received base64 image saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to decode base64 image: {e}")
            return {"success": False, "error": "Invalid base64 image"}
    else:
        frame = camera.get_frame()
        if frame is None:
            return {"success": False, "error": "Camera not available and no image provided"}
        cv2.imwrite(filepath, frame)
        logger.info(f"Captured frame saved to {filepath}")

    # 2. Call services
    results = {}
    for name, port in SERVICES.items():
        logger.info(f"Calling {name} service on port {port}...")
        url = f"http://localhost:{port}/analyze"
        svc_payload = {"image_path": filepath}
        try:
            resp = requests.post(url, json=svc_payload, timeout=5)
            if resp.status_code == 200:
                results[name] = resp.json()
            else:
                results[name] = {"error": f"Status {resp.status_code}"}
        except Exception as e:
            logger.error(f"Failed to call {name}: {e}")
            results[name] = {"error": str(e)}

    # 3. Return response with base64 image
    image_b64 = None
    try:
        with open(filepath, "rb") as img_file:
            image_b64 = base64.b64encode(img_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encode image: {e}")

    return {
        "success": True,
        "timestamp": timestamp,
        "image_path": filepath,
        "image": image_b64,
        "results": results
    }


class SkinRunRequest(BaseModel):
    user_id: Optional[str] = None


@app.post("/skin/run")
def skin_run(request: SkinRunRequest = None):
    """
    Skin-only analysis: capture frame, call skin service, return result + base64 image.
    """
    frame = camera.get_frame()
    if frame is None:
        return {"service": "skin", "error": "Camera not available", "score": 0}

    timestamp = int(time.time())
    filename = f"snapshot_skin_{timestamp}.jpg"
    filepath = os.path.join(SNAPSHOT_DIR, filename)
    cv2.imwrite(filepath, frame)

    url = f"http://localhost:{SERVICES['skin']}/analyze"
    try:
        resp = requests.post(url, json={"image_path": filepath}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Skin service call failed: {e}")
        return {"service": "skin", "error": str(e), "score": 0}

    # Add base64 image to response
    try:
        with open(filepath, "rb") as f:
            data["captured_image"] = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        pass
    if request and request.user_id:
        data["user_id"] = request.user_id
    data["images_analyzed"] = 1
    return data


@app.post("/capture-frame")
async def capture_frame():
    """
    Capture a single frame from the camera and return as base64.
    Used by backend for face recognition and enrollment (no image from frontend).
    """
    frame = camera.get_frame()
    if frame is None:
        return {"success": False, "error": "Camera not available", "image": None}
    _, jpg = cv2.imencode(".jpg", frame)
    image_b64 = base64.b64encode(jpg).decode("utf-8")
    return {"success": True, "image": image_b64}


class EyesRunRequest(BaseModel):
    user_id: Optional[str] = None


EYES_RUN_DURATION_SEC = 5.0
EYES_FRAME_INTERVAL_SEC = 0.1  # ~50 frames in 5 sec


@app.post("/eyes/run")
def eyes_run(request: EyesRunRequest = None):
    """
    Run eye strain analysis using the shared camera: capture frames for 5 seconds,
    send each frame to the eyes service stream/frame endpoint, then get aggregated
    result (EAR, blink rate, drowsiness, score) from stream/end.
    Returns result + captured_image (last frame base64) for debug overlay.
    """
    frame = camera.get_frame()
    if frame is None:
        return {"service": "eyes", "error": "Camera not available", "score": None, "details": None}

    session_id = str(uuid.uuid4())
    eyes_url = f"http://localhost:{SERVICES['eyes']}"
    start = time.time()
    last_frame_b64 = None
    frame_count = 0

    while (time.time() - start) < EYES_RUN_DURATION_SEC:
        frame = camera.get_frame()
        if frame is None:
            break
        _, jpg = cv2.imencode(".jpg", frame)
        image_b64 = base64.b64encode(jpg).decode("utf-8")
        last_frame_b64 = image_b64
        try:
            resp = requests.post(
                f"{eyes_url}/analyze/stream/frame",
                json={"session_id": session_id, "image_base64": image_b64},
                timeout=2,
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                frame_count += 1
        except Exception as e:
            logger.warning(f"Eyes stream frame failed: {e}")
        time.sleep(EYES_FRAME_INTERVAL_SEC)

    try:
        resp = requests.post(
            f"{eyes_url}/analyze/stream/end",
            json={"session_id": session_id},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Eyes stream end failed: {e}")
        return {"service": "eyes", "error": str(e), "score": None, "details": None}

    if data.get("error"):
        return {
            "service": "eyes",
            "error": data["error"],
            "score": None,
            "details": None,
            "captured_image": last_frame_b64,
        }

    data["captured_image"] = last_frame_b64
    if request and request.user_id:
        data["user_id"] = request.user_id
    data["frames_analyzed"] = data.get("frames_analyzed", frame_count)
    return data


if __name__ == "__main__":
    # Run the Orchestrator on Port 8001
    uvicorn.run(app, host="0.0.0.0", port=8001)
