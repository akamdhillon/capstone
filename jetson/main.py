"""
Clarity+ Orchestrator
=====================
Command Center.
Starts stereo cameras, saves snapshots, and orchestrates analysis via microservices.
Provides stereo calibration + user-position endpoints.
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

from typing import Optional, Tuple
import base64
import numpy as np
from pydantic import BaseModel

from config import settings, IS_MAC
from stereo import StereoCalibrator, StereoDepthEstimator, estimate_user_position

logger_cam = logging.getLogger("camera")


# ═══════════════════════════════════════════════════════════════════════════
# StereoCameraManager
# ═══════════════════════════════════════════════════════════════════════════
class StereoCameraManager:
    """Manages a stereo camera pair (Jetson) or a single webcam (Mac)."""

    def __init__(self):
        self._cap_left: Optional[cv2.VideoCapture] = None
        self._cap_right: Optional[cv2.VideoCapture] = None
        self._frame_left: Optional[np.ndarray] = None
        self._frame_right: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stereo = not IS_MAC

        self.width = settings.CAMERA_RESOLUTION_WIDTH
        self.height = settings.CAMERA_RESOLUTION_HEIGHT
        self.fps = settings.CAMERA_FPS

    def start(self) -> bool:
        if self._running:
            return True

        if IS_MAC:
            src = settings.MAC_CAMERA_INDEX
            logger_cam.info("Mac mode — opening single camera %d", src)
            self._cap_left = cv2.VideoCapture(src)
            self._configure_cap(self._cap_left)
            if not self._cap_left.isOpened():
                logger_cam.error("Failed to open Mac camera. Entering mock mode.")
                return self._start_mock()
        else:
            src_l = settings.CAMERA_DEVICE_LEFT
            src_r = settings.CAMERA_DEVICE_RIGHT
            logger_cam.info("Stereo mode — opening cameras L=%d R=%d", src_l, src_r)
            self._cap_left = cv2.VideoCapture(src_l)
            self._cap_right = cv2.VideoCapture(src_r)
            self._configure_cap(self._cap_left)
            self._configure_cap(self._cap_right)
            if not self._cap_left.isOpened():
                logger_cam.error("Left camera %d failed. Entering mock mode.", src_l)
                return self._start_mock()
            if not self._cap_right.isOpened():
                logger_cam.warning("Right camera %d failed — stereo disabled, using left only.", src_r)
                self._stereo = False

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        return True

    def _configure_cap(self, cap: cv2.VideoCapture):
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)

    def _start_mock(self) -> bool:
        self._running = True
        self._stereo = False
        self._thread = threading.Thread(target=self._mock_capture_loop, daemon=True)
        self._thread.start()
        return True

    def _mock_capture_loop(self):
        logger_cam.warning("Starting MOCK camera loop (Green screen).")
        while self._running:
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            frame[:] = (0, 255, 0)
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, f"MOCK CAMERA - {ts}", (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            with self._lock:
                self._frame_left = frame
                self._frame_right = None
            time.sleep(1.0 / self.fps)

    def _capture_loop(self):
        while self._running:
            left_ok, right_ok = False, False
            if self._cap_left:
                ret, frame = self._cap_left.read()
                if ret:
                    with self._lock:
                        self._frame_left = frame
                    left_ok = True
            if self._stereo and self._cap_right:
                ret, frame = self._cap_right.read()
                if ret:
                    with self._lock:
                        self._frame_right = frame
                    right_ok = True
            if not left_ok:
                time.sleep(0.05)
            time.sleep(1.0 / self.fps)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        for cap in (self._cap_left, self._cap_right):
            if cap:
                cap.release()

    def get_frame(self) -> Optional[np.ndarray]:
        """Return the left frame (backward-compat for all single-camera services)."""
        with self._lock:
            if self._frame_left is not None:
                return self._frame_left.copy()
        return None

    def get_stereo_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        with self._lock:
            left = self._frame_left.copy() if self._frame_left is not None else None
            right = self._frame_right.copy() if self._frame_right is not None else None
        return left, right

    @property
    def has_stereo(self) -> bool:
        return self._stereo and self._cap_right is not None and self._cap_right.isOpened()


camera = StereoCameraManager()

# Stereo calibration / depth singleton
_calibrator = StereoCalibrator()
_depth_estimator: Optional[StereoDepthEstimator] = None


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
    global _depth_estimator
    logger.info("Starting Camera...")
    if camera.start():
        logger.info("Camera started (stereo=%s).", camera.has_stereo)
    else:
        logger.error("Failed to start camera.")

    # Try to load existing stereo calibration
    calib_path = settings.STEREO_CALIB_PATH
    if _calibrator.load(calib_path):
        _depth_estimator = StereoDepthEstimator(_calibrator)
        logger.info("Stereo calibration loaded — depth estimation available.")
    else:
        logger.info("No stereo calibration found at %s — run /stereo/calibrate first.", calib_path)

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

    # 4. Optionally include stereo user position
    position = None
    if _depth_estimator and _depth_estimator.is_ready and camera.has_stereo:
        try:
            left, right = camera.get_stereo_frames()
            if left is not None and right is not None:
                depth_map = _depth_estimator.compute_depth(left, right)
                fx = _calibrator.camera_matrix_left[0, 0] * 0.5
                fy = _calibrator.camera_matrix_left[1, 1] * 0.5
                position = estimate_user_position(depth_map, fx=fx, fy=fy)
        except Exception as e:
            logger.warning("Stereo position failed during analyze: %s", e)

    return {
        "success": True,
        "timestamp": timestamp,
        "image_path": filepath,
        "image": image_b64,
        "results": results,
        "stereo_position": position,
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


# ═══════════════════════════════════════════════════════════════════════════
# Stereo Calibration & Position Endpoints
# ═══════════════════════════════════════════════════════════════════════════

class CalibrateSettings(BaseModel):
    board_cols: int = 9
    board_rows: int = 6
    square_size_mm: float = 25.0


@app.post("/stereo/calibrate/capture")
async def stereo_calibrate_capture(cfg: CalibrateSettings = None):
    """Capture one checkerboard pair and detect corners."""
    if not camera.has_stereo:
        return {"error": "Stereo cameras not available"}

    left, right = camera.get_stereo_frames()
    if left is None or right is None:
        return {"error": "Could not read stereo frames"}

    board = (cfg.board_cols, cfg.board_rows) if cfg else _calibrator.board_size
    if cfg and (board != _calibrator.board_size or cfg.square_size_mm != _calibrator.square_size_mm):
        _calibrator.__init__(board_size=board, square_size_mm=cfg.square_size_mm if cfg else 25.0)

    result = _calibrator.capture_checkerboard(left, right)

    resp = {"found": result["found"], "pair_count": _calibrator.pair_count}
    if result["found"] and "annotated_left" in result:
        _, jpg_l = cv2.imencode(".jpg", result["annotated_left"])
        _, jpg_r = cv2.imencode(".jpg", result["annotated_right"])
        resp["annotated_left"] = base64.b64encode(jpg_l).decode("utf-8")
        resp["annotated_right"] = base64.b64encode(jpg_r).decode("utf-8")
    return resp


@app.post("/stereo/calibrate/run")
async def stereo_calibrate_run():
    """Run stereo calibration with all captured pairs and save to disk."""
    global _depth_estimator
    result = _calibrator.calibrate()
    if result.get("success"):
        calib_path = settings.STEREO_CALIB_PATH
        _calibrator.save(calib_path)
        _depth_estimator = StereoDepthEstimator(_calibrator)
    return result


@app.get("/stereo/calibrate/status")
async def stereo_calibrate_status():
    """Return calibration state."""
    return {
        "calibrated": _calibrator.calibrated,
        "pairs_captured": _calibrator.pair_count,
        "baseline_m": _calibrator.baseline_m if _calibrator.calibrated else None,
        "stereo_cameras": camera.has_stereo,
    }


@app.post("/stereo/calibrate/reset")
async def stereo_calibrate_reset():
    """Discard collected pairs and start over."""
    _calibrator.reset()
    return {"status": "ok", "pairs_captured": 0}


@app.get("/stereo/position")
async def stereo_position():
    """Compute current user position from stereo depth."""
    if not camera.has_stereo:
        return {"error": "Stereo cameras not available"}
    if _depth_estimator is None or not _depth_estimator.is_ready:
        return {"error": "Stereo not calibrated — run /stereo/calibrate first"}

    left, right = camera.get_stereo_frames()
    if left is None or right is None:
        return {"error": "Could not read stereo frames"}

    try:
        depth_map = _depth_estimator.compute_depth(left, right)
        fx = _calibrator.camera_matrix_left[0, 0] * 0.5
        fy = _calibrator.camera_matrix_left[1, 1] * 0.5
        pos = estimate_user_position(depth_map, fx=fx, fy=fy)
        return {"success": True, "position": pos}
    except Exception as e:
        logger.error("Stereo position failed: %s", e)
        return {"error": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
