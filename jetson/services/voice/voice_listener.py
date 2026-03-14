"""
Clarity+ Jetson Voice Listener
==============================
Runs on Jetson: mic + Whisper STT + TTS.
Posts commands to Pi backend /voice/intent and status to Pi /api/voice/status.
"""

import logging
import os
import queue
import re
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np
import requests

logger = logging.getLogger("service.voice")

# Load .env from repo root for WHISPER_MODEL
_jet_root = Path(__file__).resolve().parent.parent.parent
_repo_root = _jet_root.parent
try:
    from dotenv import load_dotenv
    load_dotenv(_repo_root / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------
whisper = None
sd = None
pyttsx3 = None


def _ensure_imports():
    global whisper, sd, pyttsx3
    if whisper is None:
        import whisper as _w
        whisper = _w
    if sd is None:
        import sounddevice as _sd
        sd = _sd
    if pyttsx3 is None:
        import pyttsx3 as _tts
        pyttsx3 = _tts


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16000
CHUNK_SEC = 4
CHUNK_FRAMES = SAMPLE_RATE * CHUNK_SEC
COMMAND_CHUNK_SEC = 5
COMMAND_CHUNK_FRAMES = SAMPLE_RATE * COMMAND_CHUNK_SEC

WAKE_VARIANTS = [
    "hey clarity", "hey clary", "hey clari", "hey clara",
    "heyklarit", "a clarity", "hey clair", "clarity",
]


def _find_wake_word(text: str):
    lower = text.lower().strip()
    for variant in WAKE_VARIANTS:
        idx = lower.find(variant)
        if idx != -1:
            after = lower[idx + len(variant):]
            after = re.sub(r"^[,.\s!?]+", "", after).strip()
            return True, after
    return False, ""


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------
_tts_engine = None
_tts_lock = threading.Lock()


def _speak(text: str):
    if not text:
        return
    try:
        with _tts_lock:
            if _tts_engine is None:
                _ensure_imports()
                _tts_engine = pyttsx3.init()
                _tts_engine.setProperty("rate", 175)
            _tts_engine.say(text)
            _tts_engine.runAndWait()
    except Exception as e:
        logger.error("TTS error: %s", e)


# ---------------------------------------------------------------------------
# Voice Listener
# ---------------------------------------------------------------------------
class JetsonVoiceListener:
    """Voice listener on Jetson. Uses Whisper for STT, POSTs to Pi backend."""

    def __init__(self, backend_url: str):
        self._backend_url = backend_url.rstrip("/")
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._trigger_queue: queue.Queue = queue.Queue()
        self._whisper_model = None

    def _load_whisper(self):
        if self._whisper_model is not None:
            return self._whisper_model
        model_name = os.getenv("WHISPER_MODEL", "tiny")
        logger.info("Loading Whisper model: %s", model_name)
        self._whisper_model = whisper.load_model(model_name, device="cpu")
        return self._whisper_model

    def _transcribe(self, audio_i16: np.ndarray) -> str:
        audio_f32 = audio_i16.astype(np.float32) / 32768.0
        model = self._load_whisper()
        result = model.transcribe(audio_f32, fp16=False, language="en")
        return (result.get("text") or "").strip()

    def _post_status(self, state: str, caption: Optional[str] = None, transcript: Optional[str] = None):
        try:
            payload = {"state": state}
            if caption:
                payload["caption"] = caption
            if transcript:
                payload["transcript"] = transcript
            requests.post(f"{self._backend_url}/api/voice/status", json=payload, timeout=2)
        except Exception:
            pass

    def trigger_listen(self):
        try:
            self._trigger_queue.put_nowait(True)
        except queue.Full:
            pass

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="voice-listener")
        self._thread.start()
        logger.info("Jetson voice listener started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("Jetson voice listener stopped")

    def _process_command(self, command: str, raw_text: Optional[str] = None):
        transcript = raw_text or command
        self._post_status("PROCESSING", transcript=transcript)
        try:
            r = requests.post(
                f"{self._backend_url}/voice/intent",
                json={"user_text": command.strip(), "user_id": None, "display_name": None, "history": []},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            assistant_msg = data.get("assistant_message", "")
            if assistant_msg:
                self._post_status("SPEAKING", caption=assistant_msg, transcript=transcript)
                _speak(assistant_msg)
        except Exception as e:
            logger.error("Command processing failed: %s", e)
            self._post_status("SPEAKING", caption="Sorry, I had trouble with that.", transcript=transcript)
            _speak("Sorry, I had trouble with that.")
        self._post_status("IDLE")

    def _record_chunk(self, stream, num_frames: int) -> Optional[np.ndarray]:
        if not self._running:
            return None
        try:
            data, _ = stream.read(num_frames)
            return np.frombuffer(data, dtype=np.int16)
        except Exception as e:
            logger.debug("Record error: %s", e)
            return None

    def _run(self):
        try:
            _ensure_imports()
        except ImportError as e:
            logger.error("Voice listener missing dependency: %s", e)
            return

        self._load_whisper()

        try:
            stream = sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16")
        except Exception as e:
            logger.error("Failed to open microphone: %s", e)
            return

        stream.start()
        logger.info("Microphone open, listening for 'Hey Clarity'...")

        try:
            while self._running:
                # Check for trigger (skip wake word)
                try:
                    self._trigger_queue.get_nowait()
                    self._post_status("LISTENING")
                    logger.info("Trigger — recording command...")
                    chunk = self._record_chunk(stream, COMMAND_CHUNK_FRAMES)
                    if chunk is not None:
                        text = self._transcribe(chunk)
                        if text:
                            self._process_command(text, raw_text=text)
                        else:
                            self._post_status("IDLE")
                    continue
                except queue.Empty:
                    pass

                # Record chunk and check for wake word
                chunk = self._record_chunk(stream, CHUNK_FRAMES)
                if chunk is None:
                    continue

                text = self._transcribe(chunk)
                if not text:
                    continue

                found, after = _find_wake_word(text)
                if not found:
                    continue

                logger.info("Wake word detected: '%s'", after or "(recording command)")
                if after:
                    self._process_command(after, raw_text=text)
                else:
                    self._post_status("LISTENING")
                    cmd_chunk = self._record_chunk(stream, COMMAND_CHUNK_FRAMES)
                    if cmd_chunk is not None:
                        cmd_text = self._transcribe(cmd_chunk)
                        if cmd_text:
                            self._process_command(cmd_text, raw_text=cmd_text)
                        else:
                            self._post_status("IDLE")
                    else:
                        self._post_status("IDLE")

        except Exception as e:
            logger.error("Voice loop error: %s", e)
        finally:
            stream.stop()
            stream.close()
            logger.info("Microphone closed")
