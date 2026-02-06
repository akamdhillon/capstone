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
from fastapi import FastAPI, UploadFile, File
import requests
import uvicorn

from typing import Optional
import numpy as np

# --- Camera Manager ---
try:
    from config import settings, IS_MAC
except ImportError:
    class Settings:
        CAMERA_RESOLUTION_WIDTH = 1920
        CAMERA_RESOLUTION_HEIGHT = 1080
        CAMERA_FPS = 30
        MAC_CAMERA_INDEX = 0
        CAMERA_DEVICE_PRIMARY = 0
        USE_GSTREAMER = False
        DEV_MODE = False
        DEV_VIDEO_PATH = "video.mp4"
        camera_source_primary = 0
        camera_source_secondary = 1
    
    settings = Settings()
    import platform
    IS_MAC = platform.system() == "Darwin"

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
            logger_cam.error("Failed to open camera")
            return False
            
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        return True
        
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
    "posture": 8002,
    "eyes": 8003,
    "skin": 8004,
    "face": 8005,
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

@app.post("/analyze")
async def analyze_endpoint(file: UploadFile = File(None)):
    """
    Main entry point for analysis.
    If file is provided, uses that.
    If no file provided, captures from live camera.
    """
    timestamp = int(time.time())
    filename = f"snapshot_{timestamp}.jpg"
    filepath = os.path.join(SNAPSHOT_DIR, filename)
    
    # 1. Acquire Image
    if file:
        contents = await file.read()
        with open(filepath, "wb") as f:
            f.write(contents)
        logger.info(f"Received file saved to {filepath}")
    else:
        # Capture from camera
        frame = camera.get_frame()
        if frame is None:
            return {"error": "Camera not available and no file uploaded"}
        cv2.imwrite(filepath, frame)
        logger.info(f"captured frame saved to {filepath}")

    # 2. Call Services
    results = {}
    
    for name, port in SERVICES.items():
        logger.info(f"Calling {name} service on port {port}...")
        url = f"http://localhost:{port}/analyze"
        payload = {"image_path": filepath}
        
        try:
            # Short timeout since these are local
            resp = requests.post(url, json=payload, timeout=2)
            if resp.status_code == 200:
                results[name] = resp.json()
            else:
                results[name] = {"error": f"Status {resp.status_code}"}
        except Exception as e:
            logger.error(f"Failed to call {name}: {e}")
            results[name] = {"error": str(e)}

    # 3. Prepare Response (include image as base64)
    import base64
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
    uvicorn.run(app, host="192.168.10.2", port=8001)
