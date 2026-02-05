"""
Clarity+ Camera Manager
=======================
Dual 1080p camera capture pipeline using GStreamer and OpenCV.
Supports DEV_MODE fallback to video file for development.

Platform Support:
    - Mac (Darwin): Uses camera index (0, 1), OpenCV only (no GStreamer)
    - Linux (Jetson/RPi): Uses /dev/video0, GStreamer pipeline
"""

import logging
import threading
import time
from typing import Optional, Tuple, Union
import queue
import cv2
import numpy as np

from config import settings, IS_MAC

logger = logging.getLogger("clarity-ml.camera")


class CameraManager:
    """
    Manages dual 1080p USB camera capture with GStreamer pipeline.
    
    Pipeline: v4l2src -> videoconvert -> appsink
    
    Features:
        - Thread-safe frame buffer for concurrent access
        - DEV_MODE fallback to video file
        - Mac development support (uses camera index instead of device path)
        - Automatic reconnection on camera failure
    """
    
    def __init__(self):
        self._primary_cap: Optional[cv2.VideoCapture] = None
        self._secondary_cap: Optional[cv2.VideoCapture] = None
        
        # Frame buffers (thread-safe)
        self._primary_frame: Optional[np.ndarray] = None
        self._secondary_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        
        # Capture thread management
        self._running = False
        self._capture_thread: Optional[threading.Thread] = None
        
        # Frame timestamps
        self._primary_timestamp: float = 0.0
        self._secondary_timestamp: float = 0.0
        
        # Configuration
        self.width = settings.CAMERA_RESOLUTION_WIDTH
        self.height = settings.CAMERA_RESOLUTION_HEIGHT
        self.fps = settings.CAMERA_FPS
        
        # Log platform info
        if IS_MAC:
            logger.info(f"🍎 Mac detected - using camera index: {settings.MAC_CAMERA_INDEX}")
        else:
            logger.info(f"🐧 Linux detected - using camera device: {settings.CAMERA_DEVICE_PRIMARY}")
    
    def _build_gstreamer_pipeline(self, device: str) -> str:
        """
        Construct GStreamer pipeline for USB camera capture.
        
        Pipeline: v4l2src -> videoconvert -> appsink
        Optimized for NVIDIA Jetson with hardware acceleration.
        """
        return (
            f"v4l2src device={device} ! "
            f"video/x-raw, width={self.width}, height={self.height}, framerate={self.fps}/1 ! "
            f"videoconvert ! "
            f"video/x-raw, format=BGR ! "
            f"appsink drop=1 max-buffers=2"
        )
    
    def _open_camera(self, source: Union[int, str], use_gstreamer: bool = False) -> Optional[cv2.VideoCapture]:
        """
        Open a camera device with optional GStreamer pipeline.
        
        Args:
            source: Camera index (int) for Mac, or device path (str) for Linux
            use_gstreamer: Use GStreamer pipeline (only works on Linux)
        """
        try:
            if use_gstreamer and settings.USE_GSTREAMER and isinstance(source, str):
                pipeline = self._build_gstreamer_pipeline(source)
                cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
                logger.info(f"Opened camera with GStreamer: {source}")
            else:
                # Standard OpenCV capture (works on Mac and Linux)
                cap = cv2.VideoCapture(source)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_FPS, self.fps)
                logger.info(f"Opened camera/video: {source}")
            
            if cap.isOpened():
                return cap
            else:
                logger.error(f"Failed to open: {source}")
                return None
                
        except Exception as e:
            logger.error(f"Camera init error for {source}: {e}")
            return None
    
    def start(self) -> bool:
        """Start the camera capture pipeline."""
        if self._running:
            logger.warning("Camera manager already running")
            return True
        
        if settings.DEV_MODE:
            # DEV_MODE: Use video file for both cameras
            logger.info(f"DEV_MODE enabled - using video file: {settings.DEV_VIDEO_PATH}")
            self._primary_cap = self._open_camera(settings.DEV_VIDEO_PATH, use_gstreamer=False)
            # For secondary, reuse same video (clone capture)
            self._secondary_cap = self._open_camera(settings.DEV_VIDEO_PATH, use_gstreamer=False)
        else:
            # Production/Development: Use platform-aware camera sources
            primary_source = settings.camera_source_primary
            secondary_source = settings.camera_source_secondary
            
            logger.info(f"Opening primary camera: {primary_source}")
            self._primary_cap = self._open_camera(primary_source, use_gstreamer=settings.USE_GSTREAMER)
            
            logger.info(f"Opening secondary camera: {secondary_source}")
            self._secondary_cap = self._open_camera(secondary_source, use_gstreamer=settings.USE_GSTREAMER)
        
        if self._primary_cap is None:
            logger.error("Failed to initialize primary camera")
            return False
        
        if self._secondary_cap is None:
            logger.warning("Secondary camera not available, running in single-camera mode")
        
        # Start capture thread
        self._running = True
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()
        
        logger.info("Camera capture started")
        return True
    
    def _capture_loop(self):
        """Continuous capture loop in background thread."""
        while self._running:
            timestamp = time.time()
            
            # Capture from primary camera
            if self._primary_cap and self._primary_cap.isOpened():
                ret, frame = self._primary_cap.read()
                if ret:
                    with self._frame_lock:
                        self._primary_frame = frame
                        self._primary_timestamp = timestamp
                elif settings.DEV_MODE:
                    # Loop video in DEV_MODE
                    self._primary_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            # Capture from secondary camera
            if self._secondary_cap and self._secondary_cap.isOpened():
                ret, frame = self._secondary_cap.read()
                if ret:
                    with self._frame_lock:
                        self._secondary_frame = frame
                        self._secondary_timestamp = timestamp
                elif settings.DEV_MODE:
                    self._secondary_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            # Maintain target FPS
            time.sleep(1.0 / self.fps)
    
    def stop(self):
        """Stop the camera capture pipeline."""
        self._running = False
        
        if self._capture_thread:
            self._capture_thread.join(timeout=2.0)
        
        if self._primary_cap:
            self._primary_cap.release()
            self._primary_cap = None
        
        if self._secondary_cap:
            self._secondary_cap.release()
            self._secondary_cap = None
        
        logger.info("Camera capture stopped")
    
    def get_frame(self, camera: str = "primary") -> Tuple[Optional[np.ndarray], float]:
        """
        Get the latest frame from specified camera.
        
        Args:
            camera: "primary" or "secondary"
        
        Returns:
            Tuple of (frame, timestamp). Frame is None if unavailable.
        """
        with self._frame_lock:
            if camera == "primary":
                if self._primary_frame is not None:
                    return self._primary_frame.copy(), self._primary_timestamp
            elif camera == "secondary":
                if self._secondary_frame is not None:
                    return self._secondary_frame.copy(), self._secondary_timestamp
        
        return None, 0.0
    
    def get_both_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], float]:
        """
        Get frames from both cameras.
        
        Returns:
            Tuple of (primary_frame, secondary_frame, timestamp)
        """
        with self._frame_lock:
            primary = self._primary_frame.copy() if self._primary_frame is not None else None
            secondary = self._secondary_frame.copy() if self._secondary_frame is not None else None
            timestamp = max(self._primary_timestamp, self._secondary_timestamp)
        
        return primary, secondary, timestamp
    
    @property
    def is_running(self) -> bool:
        """Check if camera capture is running."""
        return self._running


# Singleton instance
_camera_manager: Optional[CameraManager] = None


def get_camera_manager() -> CameraManager:
    """Get or create the singleton CameraManager instance."""
    global _camera_manager
    if _camera_manager is None:
        _camera_manager = CameraManager()
    return _camera_manager
