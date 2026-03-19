# =============================================================================
# CLARITY+ BACKEND - CONFIGURATION
# =============================================================================


import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from repo root
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Settings:
    # Network
    SERVICES_HOST = os.getenv("SERVICES_HOST", "localhost")
    RPI_IP = os.getenv("RPI_IP")
    # Backend base URL for self-calls (voice orchestrator, navigate); uses RPI_IP
    BACKEND_BASE_URL = f"http://{os.getenv('RPI_IP')}:8000" if os.getenv("RPI_IP") else None

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/clarity.db")
    
    # Feature Toggles
    DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Security - AES-256 requires 32 bytes (256 bits)
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "clarity_default_key_change_in_prod!")
    
    # Janitor Configuration
    IMAGE_RETENTION_DAYS = os.getenv("IMAGE_RETENTION_DAYS", "30")
    JANITOR_SCHEDULE_HOUR = os.getenv("JANITOR_SCHEDULE_HOUR", "2")
    
    # LLM
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")

    # Service Ports
    SERVICES_FACE_PORT = 8002
    SERVICES_SKIN_PORT = 8003
    SERVICES_POSTURE_PORT = 8004
    SERVICES_EYES_PORT = 8005
    
    weights = {
        "skin": 0.40,
        "posture": 0.35,
        "eyes": 0.25,
    }


settings = Settings()
is_mac = os.uname().sysname == "Darwin"
IS_MAC = is_mac