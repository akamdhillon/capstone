import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from parent directory (repo root) if it exists, otherwise local
# repo root is two levels up if we are in jetson/
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Settings:
    # Network
    JETSON_IP = os.getenv("JETSON_IP", "192.168.2.2")
    RPI_IP = os.getenv("RPI_IP", "192.168.2.1")
    
    # Camera defaults (can be overridden by env if needed, but keeping simple for now)
    CAMERA_RESOLUTION_WIDTH = 1920
    CAMERA_RESOLUTION_HEIGHT = 1080
    CAMERA_FPS = 30
    MAC_CAMERA_INDEX = int(os.getenv("MAC_CAMERA_INDEX", "0"))
    CAMERA_DEVICE_PRIMARY = 0
    USE_GSTREAMER = False
    DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
    DEV_VIDEO_PATH = "video.mp4"

settings = Settings()
is_mac = os.uname().sysname == "Darwin"
IS_MAC = is_mac
