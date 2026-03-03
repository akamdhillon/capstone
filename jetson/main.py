"""
Clarity+ Orchestrator
=====================
Command Center.
Starts camera, saves snapshots, and orchestrates analysis via microservices.
"""

import sys
import os
import time
import logging
import cv2
import threading
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

app = FastAPI(title="Clarity+ Orchestrator")
logger = logging.getLogger("orchestrator")
logging.basicConfig(level=logging.INFO)

@app.on_event("startup")
def startup():
    logger.info("Starting Camera...")
    if camera.start():
        logger.info("Camera started.")
    else:
        logger.error("Failed to start camera.")

@app.on_event("shutdown")
def shutdown():
    logger.info("Stopping Camera...")
    camera.stop()

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

    # 1. Acquire image — prefer base64 payload, fall back to camera
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

if __name__ == "__main__":
    # Run the Orchestrator on Port 8001
    uvicorn.run(app, host="0.0.0.0", port=8001)
