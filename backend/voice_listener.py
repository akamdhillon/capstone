"""
Clarity+ Backend Voice Listener
================================
Continuous microphone listener that uses Vosk for local speech-to-text.
Detects "Hey Clarity" wake word, captures the command, processes it via
the voice_orchestrator, and speaks the response via pyttsx3.

Runs as a background thread started from main.py lifespan.
"""

import asyncio
import json
import logging
import os
import queue
import re
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports — these are heavy and may not be installed in test envs
# ---------------------------------------------------------------------------
vosk = None
sd = None
pyttsx3 = None


def _ensure_imports():
    global vosk, sd, pyttsx3
    if vosk is None:
        import vosk as _vosk
        vosk = _vosk
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
BLOCK_SIZE = 4000  # ~250 ms at 16 kHz

WAKE_VARIANTS = [
    "hey clarity",
    "hey clary",
    "hey clari",
    "hey clara",
    "heyklarit",
    "a clarity",
    "hey clair",
    "clarity",
]

COMMAND_TIMEOUT = 8.0  # seconds to wait for a command after wake word
SILENCE_TIMEOUT = 2.0  # seconds of silence to consider the command done

# Vosk model directory — will be auto-downloaded on first run
_THIS_DIR = Path(__file__).resolve().parent
MODEL_DIR = _THIS_DIR / "vosk-model"


def _find_wake_word(text: str) -> tuple[bool, str]:
    """Return (found, text_after_wake)."""
    lower = text.lower().strip()
    for variant in WAKE_VARIANTS:
        idx = lower.find(variant)
        if idx != -1:
            after = lower[idx + len(variant):]
            after = re.sub(r'^[,.\s!?]+', '', after).strip()
            return True, after
    return False, ""


# ---------------------------------------------------------------------------
# TTS Helper
# ---------------------------------------------------------------------------
_tts_engine = None
_tts_lock = threading.Lock()


def _speak(text: str):
    """Speak text using pyttsx3 (blocking, thread-safe)."""
    global _tts_engine
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
        logger.error(f"TTS error: {e}")


# ---------------------------------------------------------------------------
# Voice Listener
# ---------------------------------------------------------------------------
class VoiceListener:
    """
    Background voice listener that:
    1. Opens mic via sounddevice → queue → Vosk recognizer
    2. Detects "Hey Clarity" wake word
    3. Captures the command
    4. Calls voice_orchestrator.process_voice_intent() in-process
    5. Speaks the response via pyttsx3
    6. Pushes state updates over WebSocket via ConnectionManager
    """

    def __init__(self, ws_manager, event_loop: asyncio.AbstractEventLoop):
        self._manager = ws_manager
        self._loop = event_loop
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="voice-listener")
        self._thread.start()
        logger.info("Voice listener started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("Voice listener stopped")

    # -- WebSocket broadcast helpers (thread-safe via event loop) --

    def _broadcast(self, data: dict):
        """Schedule a WebSocket broadcast on the main asyncio loop."""
        try:
            asyncio.run_coroutine_threadsafe(
                self._manager.broadcast(data), self._loop
            )
        except Exception:
            pass

    def _set_state(self, state: str, caption: Optional[str] = None, transcript: Optional[str] = None):
        msg = {"state": state}
        if caption:
            msg["caption"] = caption
        if transcript:
            msg["transcript"] = transcript
        self._broadcast(msg)

    # -- Audio callback for sounddevice --

    def _audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio block. Puts raw bytes in queue."""
        if status:
            logger.warning(f"Audio status: {status}")
        self._audio_queue.put(bytes(indata))

    # -- Main listener loop --

    def _run(self):
        try:
            _ensure_imports()
        except ImportError as e:
            logger.error(f"Voice listener cannot start — missing dependency: {e}")
            return

        # --- Load or download Vosk model ---
        if not MODEL_DIR.exists():
            logger.info("Vosk model not found. Downloading small English model...")
            try:
                import urllib.request
                import zipfile
                import tempfile

                model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    tmp_path = tmp.name
                    logger.info(f"Downloading {model_url} ...")
                    urllib.request.urlretrieve(model_url, tmp_path)

                logger.info("Extracting model...")
                with zipfile.ZipFile(tmp_path, "r") as zf:
                    zf.extractall(_THIS_DIR)

                os.unlink(tmp_path)

                # The zip extracts to vosk-model-small-en-us-0.15/ — rename
                extracted = _THIS_DIR / "vosk-model-small-en-us-0.15"
                if extracted.exists():
                    extracted.rename(MODEL_DIR)

                logger.info(f"Vosk model ready at {MODEL_DIR}")
            except Exception as e:
                logger.error(f"Failed to download Vosk model: {e}")
                logger.error("Please manually download a model from https://alphacephei.com/vosk/models")
                logger.error(f"Extract it to: {MODEL_DIR}")
                return

        # Suppress Vosk logs
        vosk.SetLogLevel(-1)

        try:
            model = vosk.Model(str(MODEL_DIR))
        except Exception as e:
            logger.error(f"Failed to load Vosk model from {MODEL_DIR}: {e}")
            return

        logger.info("Vosk model loaded successfully")

        recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)

        # --- Open microphone via sounddevice ---
        try:
            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
            ):
                logger.info("Microphone listening — say 'Hey Clarity'")
                while self._running:
                    self._listen_for_wake(recognizer)
        except Exception as e:
            logger.error(f"Failed to open microphone: {e}")
            return

        logger.info("Microphone closed")

    def _read_audio_block(self, timeout: float = 0.5) -> Optional[bytes]:
        """Read one audio block from the queue (non-blocking with timeout)."""
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _listen_for_wake(self, recognizer):
        """Block until wake word is detected, then capture + process command."""
        data = self._read_audio_block()
        if data is None or not self._running:
            return

        if recognizer.AcceptWaveform(data):
            result = json.loads(recognizer.Result())
            text = result.get("text", "")
            if not text:
                return

            found, after = _find_wake_word(text)
            if not found:
                return

            logger.info(f"Wake word detected! After wake: '{after}'")

            if after:
                # Wake word + command in the same utterance
                self._process_command(after, raw_text=text)
            else:
                # Wake word only — listen for the command
                self._set_state("LISTENING")
                logger.info("Listening for command...")
                command = self._capture_command(recognizer)
                if command:
                    self._process_command(command, raw_text=command)
                else:
                    logger.info("No command heard, returning to idle")
                    self._set_state("IDLE")
        else:
            # Check partial results for wake word too (faster detection)
            partial = json.loads(recognizer.PartialResult())
            partial_text = partial.get("partial", "")
            if partial_text:
                found, after = _find_wake_word(partial_text)
                if found and not after:
                    # Wake heard in partial — wait for final result
                    pass

    def _capture_command(self, recognizer) -> Optional[str]:
        """After wake word, listen for up to COMMAND_TIMEOUT seconds for a command."""
        start = time.time()
        last_speech_time = time.time()

        while self._running and (time.time() - start) < COMMAND_TIMEOUT:
            data = self._read_audio_block()
            if data is None:
                continue

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    # Strip any repeated wake word from the command
                    _, cleaned = _find_wake_word(text)
                    return cleaned if cleaned else text
            else:
                partial = json.loads(recognizer.PartialResult())
                if partial.get("partial", "").strip():
                    last_speech_time = time.time()

            # If silence for too long after some speech, stop
            if (time.time() - last_speech_time) > SILENCE_TIMEOUT and (time.time() - start) > 2.0:
                # No speech for a while — check final
                result = json.loads(recognizer.FinalResult())
                text = result.get("text", "").strip()
                if text:
                    _, cleaned = _find_wake_word(text)
                    return cleaned if cleaned else text
                return None

        # Timeout — grab whatever is there
        result = json.loads(recognizer.FinalResult())
        text = result.get("text", "").strip()
        if text:
            _, cleaned = _find_wake_word(text)
            return cleaned if cleaned else text
        return None

    def _process_command(self, command: str, raw_text: Optional[str] = None):
        """Send command through the voice orchestrator and speak the response."""
        logger.info(f"Processing command: '{command}'")
        transcript = raw_text or command
        self._set_state("PROCESSING", transcript=transcript)

        try:
            # Import here to avoid circular imports
            from voice_orchestrator import process_voice_intent, VoiceIntentRequest

            request = VoiceIntentRequest(
                user_text=command.strip(),
                user_id=None,
                display_name=None,
                history=[],
            )

            # Run the async orchestrator function from this sync thread
            future = asyncio.run_coroutine_threadsafe(
                process_voice_intent(request), self._loop
            )
            response = future.result(timeout=30)

            assistant_msg = response.assistant_message
            logger.info(f"Intent: {response.intent}, Message: {assistant_msg}")

            if assistant_msg:
                self._set_state("SPEAKING", assistant_msg, transcript=transcript)
                _speak(assistant_msg)

        except Exception as e:
            logger.error(f"Command processing failed: {e}")
            self._set_state("SPEAKING", "Sorry, I had trouble with that.", transcript=transcript)
            _speak("Sorry, I had trouble with that.")

        self._set_state("IDLE")
