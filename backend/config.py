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
    
    # Feature Toggles
    DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # LLM
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_STARTUP_TIMEOUT_SEC = float(os.getenv("OLLAMA_STARTUP_TIMEOUT_SEC", "5"))

    # Service Ports
    SERVICES_FACE_PORT = 8002
    SERVICES_SKIN_PORT = 8003
    SERVICES_POSTURE_PORT = 8004
    SERVICES_EYES_PORT = 8005

    # Voice (wake word + STT)
    # RealtimeSTT uses Porcupine via pvporcupine for wake word detection.
    WAKE_WORDS = os.getenv("WAKE_WORDS", "jarvis")
    WAKE_WORD_SENSITIVITY = float(os.getenv("WAKE_WORD_SENSITIVITY", "0.6"))

    # VAD / turn-taking tuning (RealtimeSTT)
    SILERO_SENSITIVITY = float(os.getenv("SILERO_SENSITIVITY", "0.5"))
    WEBRTC_SENSITIVITY = int(os.getenv("WEBRTC_SENSITIVITY", "3"))
    POST_SPEECH_SILENCE_DURATION = float(os.getenv("POST_SPEECH_SILENCE_DURATION", "0.3"))

    # Porcupine wake-word timeout
    WAKE_WORD_TIMEOUT = float(os.getenv("WAKE_WORD_TIMEOUT", "5"))

    # Transcription model (mlx-whisper)
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "mlx-community/whisper-large-v3-turbo")

    # Optional noise suppression preprocessor (SpeexDSP)
    SPEEX_NOISE_SUPPRESSION = os.getenv("SPEEX_NOISE_SUPPRESSION", "false").lower() == "true"
    SPEEX_FRAME_SIZE = int(os.getenv("SPEEX_FRAME_SIZE", "256"))
    
    weights = {
        "skin": 0.40,
        "posture": 0.35,
        "eyes": 0.25,
    }


settings = Settings()
is_mac = os.uname().sysname == "Darwin"
IS_MAC = is_mac