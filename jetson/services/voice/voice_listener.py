"""
Clarity+ Jetson Voice Listener
==============================
Runs on Jetson: mic + Vosk STT + TTS.
Posts commands to Pi backend /voice/intent and status to Pi /api/voice/status.
"""

import json
import logging
import os
import queue
import re
import threading
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("service.voice")

# ---------------------------------------------------------------------------
# Lazy imports
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
VOSK_SAMPLE_RATE = 16000
_vo = os.getenv("VOICE_MIC_RATE", "").strip()
_is_linux = os.uname().sysname == "Linux"
MIC_RATES_TO_TRY = (
    [int(_vo)] if _vo.isdigit()
    else ([16000, 44100, 48000] if _is_linux else [16000, 44100, 48000])
)

WAKE_VARIANTS = [
    "hey clarity", "hey clary", "hey clari", "hey clara",
    "heyklarit", "a clarity", "hey clair", "clarity",
]

COMMAND_TIMEOUT = 8.0
SILENCE_TIMEOUT = 2.0

_THIS_DIR = Path(__file__).resolve().parent
MODEL_DIR = _THIS_DIR / "vosk-model"


def _resample_to_16k(data: bytes, orig_rate: int) -> bytes:
    import numpy as np
    if orig_rate == VOSK_SAMPLE_RATE:
        return data
    arr = np.frombuffer(data, dtype=np.int16)
    n_target = int(len(arr) * VOSK_SAMPLE_RATE / orig_rate)
    x_old = np.linspace(0, 1, len(arr))
    x_new = np.linspace(0, 1, n_target, endpoint=False)
    resampled = np.interp(x_new, x_old, arr.astype(np.float64)).astype(np.int16)
    return resampled.tobytes()


def _find_wake_word(text: str):
    lower = text.lower().strip()
    for variant in WAKE_VARIANTS:
        idx = lower.find(variant)
        if idx != -1:
            after = lower[idx + len(variant):]
            after = re.sub(r'^[,.\s!?]+', '', after).strip()
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
    """Voice listener on Jetson. POSTs to Pi backend for intent + status."""

    def __init__(self, backend_url: str):
        self._backend_url = backend_url.rstrip("/")
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue(maxsize=48)
        self._trigger_queue: queue.Queue = queue.Queue()

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

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            logger.debug("Audio status: %s", status)
        try:
            self._audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            pass

    def _read_audio_block(self, timeout: float = 0.5) -> Optional[bytes]:
        try:
            raw = self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
        rate = getattr(self, "_mic_rate", VOSK_SAMPLE_RATE)
        if rate != VOSK_SAMPLE_RATE:
            raw = _resample_to_16k(raw, rate)
        return raw

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

    def _listen_for_wake(self, recognizer):
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
            logger.info("Wake word detected: '%s'", after or "(listening for command)")
            if after:
                self._process_command(after, raw_text=text)
            else:
                self._post_status("LISTENING")
                command = self._capture_command(recognizer)
                if command:
                    self._process_command(command, raw_text=command)
                else:
                    self._post_status("IDLE")

    def _capture_command(self, recognizer) -> Optional[str]:
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
                    _, cleaned = _find_wake_word(text)
                    return cleaned if cleaned else text
            else:
                partial = json.loads(recognizer.PartialResult())
                if partial.get("partial", "").strip():
                    last_speech_time = time.time()
            if (time.time() - last_speech_time) > SILENCE_TIMEOUT and (time.time() - start) > 2.0:
                result = json.loads(recognizer.FinalResult())
                text = result.get("text", "").strip()
                if text:
                    _, cleaned = _find_wake_word(text)
                    return cleaned if cleaned else text
                return None
        result = json.loads(recognizer.FinalResult())
        text = result.get("text", "").strip()
        if text:
            _, cleaned = _find_wake_word(text)
            return cleaned if cleaned else text
        return None

    def _run(self):
        try:
            _ensure_imports()
        except ImportError as e:
            logger.error("Voice listener missing dependency: %s", e)
            return

        if not MODEL_DIR.exists():
            logger.info("Downloading Vosk model...")
            try:
                import urllib.request
                import zipfile
                import tempfile
                url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    urllib.request.urlretrieve(url, tmp.name)
                with zipfile.ZipFile(tmp.name, "r") as zf:
                    zf.extractall(_THIS_DIR)
                os.unlink(tmp.name)
                extracted = _THIS_DIR / "vosk-model-small-en-us-0.15"
                if extracted.exists():
                    extracted.rename(MODEL_DIR)
            except Exception as e:
                logger.error("Failed to download Vosk model: %s", e)
                return

        vosk.SetLogLevel(-1)
        try:
            model = vosk.Model(str(MODEL_DIR))
        except Exception as e:
            logger.error("Failed to load Vosk: %s", e)
            return

        recognizer = vosk.KaldiRecognizer(model, VOSK_SAMPLE_RATE)
        stream = None
        for rate in MIC_RATES_TO_TRY:
            try:
                self._mic_rate = rate
                block_sec = 0.2 if _is_linux else 0.25
                blocksize = int(block_sec * rate)
                stream = sd.RawInputStream(
                    samplerate=rate, blocksize=blocksize, dtype="int16", channels=1,
                    callback=self._audio_callback, latency="high" if _is_linux else "low",
                )
                logger.info("Microphone at %s Hz", rate)
                break
            except Exception as e:
                if "Invalid sample rate" in str(e) or "-9997" in str(e):
                    continue
                raise
        if stream is None:
            logger.error("No supported mic rate in %s", MIC_RATES_TO_TRY)
            return

        try:
            with stream:
                while self._running:
                    try:
                        self._trigger_queue.get_nowait()
                        self._post_status("LISTENING")
                        command = self._capture_command(recognizer)
                        if command:
                            self._process_command(command, raw_text=command)
                        else:
                            self._post_status("IDLE")
                        continue
                    except queue.Empty:
                        pass
                    self._listen_for_wake(recognizer)
        except Exception as e:
            logger.error("Mic error: %s", e)
        logger.info("Microphone closed")
