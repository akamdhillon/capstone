import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from parent directory (repo root) if it exists, otherwise local
# repo root is two levels up if we are in jetson/
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Settings:
    # Deployment Target
    JETSON_TARGET = os.getenv("JETSON_TARGET")

    # Network
    JETSON_IP = os.getenv("JETSON_IP")
    BACKEND_IP = os.getenv("BACKEND_IP")
    
    # Camera defaults
    CAMERA_RESOLUTION_WIDTH = 1920
    CAMERA_RESOLUTION_HEIGHT = 1080
    CAMERA_FPS = 30
    MAC_CAMERA_INDEX = int(os.getenv("MAC_CAMERA_INDEX", "0"))

    # Stereo pair (Jetson): left / right USB camera indices
    CAMERA_DEVICE_LEFT = int(os.getenv("CAMERA_DEVICE_LEFT", "2"))
    CAMERA_DEVICE_RIGHT = int(os.getenv("CAMERA_DEVICE_RIGHT", "3"))
    # Single-camera services default to the left stereo cam
    CAMERA_DEVICE_PRIMARY = CAMERA_DEVICE_LEFT

    USE_GSTREAMER = os.getenv("USE_GSTREAMER", "false").lower() == "true"
    DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
    DEV_VIDEO_PATH = "video.mp4"

    # Stereo calibration file path
    STEREO_CALIB_PATH = os.getenv(
        "STEREO_CALIB_PATH",
        str(Path(__file__).resolve().parent / "calibration" / "stereo_calib.npz"),
    )

settings = Settings()
is_mac = os.uname().sysname == "Darwin"
IS_MAC = is_mac
