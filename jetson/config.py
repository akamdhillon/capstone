"""
Clarity+ Jetson ML Service Layer Configuration
===============================================
Centralized configuration using Pydantic settings with environment variable support.
All feature toggles and model paths are managed here.

Platform Support:
    - Mac (Darwin): Uses camera index (0, 1, etc.), no GStreamer
    - Linux (Jetson/RPi): Uses /dev/video0, GStreamer pipeline
"""

import os
import platform
from typing import Optional, Union
from pydantic_settings import BaseSettings
from pydantic import Field

# Platform detection
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # -------------------------------------------------------------------------
    # Feature Toggles
    # -------------------------------------------------------------------------
    ENABLE_THERMAL: bool = Field(
        default=False,
        description="Enable thermal sensor endpoint (Port 8005). Ghost service returns null when disabled."
    )
    DEV_MODE: bool = Field(
        default=False,
        description=\"When True, use video file instead of physical cameras.\"
    )
    
    # -------------------------------------------------------------------------
    # Camera Configuration
    # -------------------------------------------------------------------------
    CAMERA_DEVICE_PRIMARY: str = Field(
        default="/dev/video0",
        description="Primary USB camera device path (Linux)."
    )
    CAMERA_DEVICE_SECONDARY: str = Field(
        default="/dev/video1",
        description="Secondary USB camera device path (Linux)."
    )
    
    # Mac camera settings (uses integer index, not device path)
    MAC_CAMERA_INDEX: int = Field(
        default=0,
        description="Mac camera index. 0=built-in FaceTime, 1+=USB cameras."
    )
    
    CAMERA_RESOLUTION_WIDTH: int = Field(default=1920, description="Capture width (1080p).")
    CAMERA_RESOLUTION_HEIGHT: int = Field(default=1080, description="Capture height (1080p).")
    CAMERA_FPS: int = Field(default=30, description="Target frames per second.")
    
    # Development mode video fallback
    DEV_VIDEO_PATH: str = Field(
        default="/app/test_media/sample_video.mp4",
        description="Video file path for DEV_MODE."
    )
    
    @property
    def USE_GSTREAMER(self) -> bool:
        """GStreamer is only available on Linux (Jetson/RPi), not Mac."""
        return IS_LINUX and not self.DEV_MODE
    
    @property
    def camera_source_primary(self) -> Union[int, str]:
        """Get the primary camera source based on platform."""
        if IS_MAC:
            return self.MAC_CAMERA_INDEX
        return self.CAMERA_DEVICE_PRIMARY
    
    @property
    def camera_source_secondary(self) -> Union[int, str]:
        """Get the secondary camera source based on platform."""
        if IS_MAC:
            return self.MAC_CAMERA_INDEX + 1 if self.MAC_CAMERA_INDEX >= 0 else 1
        return self.CAMERA_DEVICE_SECONDARY
    
    # -------------------------------------------------------------------------
    # TensorRT & Model Configuration
    # -------------------------------------------------------------------------
    MODEL_PRECISION: str = Field(
        default="FP16",
        description="TensorRT precision mode: FP16 or FP32."
    )
    MODEL_DIR: str = Field(
        default="/app/models",
        description="Directory containing TensorRT engine files."
    )
    
    # Model file paths (TensorRT engines)
    YOLOV8_ENGINE_PATH: Optional[str] = Field(
        default=None,
        description="Path to YOLOv8n TensorRT engine for skin analysis."
    )
    RETINAFACE_ENGINE_PATH: Optional[str] = Field(
        default=None,
        description="Path to RetinaFace TensorRT engine for face detection."
    )
    FACENET_ENGINE_PATH: Optional[str] = Field(
        default=None,
        description="Path to FaceNet512 TensorRT engine for embeddings."
    )
    
    # -------------------------------------------------------------------------
    # Service Configuration
    # -------------------------------------------------------------------------
    HOST: str = Field(default="0.0.0.0", description="Service bind address.")
    
    # Port assignments per service
    FACE_RECOGNITION_PORT: int = Field(default=8001, description="Face recognition service port.")
    SKIN_ANALYSIS_PORT: int = Field(default=8002, description="Skin analysis service port.")
    POSTURE_PORT: int = Field(default=8003, description="Posture detection service port.")
    EYE_STRAIN_PORT: int = Field(default=8004, description="Eye strain service port.")
    THERMAL_PORT: int = Field(default=8005, description="Thermal service port (ghost service).")
    
    # -------------------------------------------------------------------------
    # Network Configuration
    # -------------------------------------------------------------------------
    RPI_GATEWAY_IP: str = Field(
        default="192.168.10.1",
        description="Raspberry Pi orchestrator IP for callbacks."
    )
    
    # -------------------------------------------------------------------------
    # Performance Targets
    # -------------------------------------------------------------------------
    INFERENCE_TIMEOUT_MS: int = Field(
        default=100,
        description="Target inference time per frame in milliseconds."
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_model_path(model_name: str) -> str:
    """Construct full path to a model file in the models directory."""
    return os.path.join(settings.MODEL_DIR, model_name)


def is_tensorrt_available() -> bool:
    """Check if TensorRT runtime is available on this system."""
    try:
        import tensorrt
        return True
    except ImportError:
        return False


def get_precision_dtype():
    """Get numpy dtype based on MODEL_PRECISION setting."""
    import numpy as np
    if settings.MODEL_PRECISION == "FP16":
        return np.float16
    return np.float32
