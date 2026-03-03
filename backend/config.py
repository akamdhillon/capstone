# =============================================================================
# CLARITY+ BACKEND - CONFIGURATION
# =============================================================================


import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from parent directory (repo root) if it exists, otherwise local
# repo root is two levels up if we are in jetson/
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Settings:
    # Network
    JETSON_IP = os.getenv("JETSON_IP")
    RPI_IP = os.getenv("RPI_IP")
    
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/clarity.db")
    
    # Feature Toggles
    THERMAL_ENABLED = os.getenv("THERMAL_ENABLED", "false").lower() == "true"
    DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Security - AES-256 requires 32 bytes (256 bits)
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "clarity_default_key_change_in_prod!")
    
    # Janitor Configuration
    IMAGE_RETENTION_DAYS = os.getenv("IMAGE_RETENTION_DAYS", "30")
    JANITOR_SCHEDULE_HOUR = os.getenv("JANITOR_SCHEDULE_HOUR", "2")
    
    # Jetson Service Ports
    JETSON_FACE_PORT = 8002
    JETSON_SKIN_PORT = 8003
    JETSON_POSTURE_PORT = 8004
    JETSON_EYE_PORT = 8005
    JETSON_THERMAL_PORT = 8006
    
    weights = {
        "skin": 0.40,
        "posture": 0.35,
        "eyes": 0.25,
        "thermal": 0.00
    }


settings = Settings()
is_mac = os.uname().sysname == "Darwin"
IS_MAC = is_mac