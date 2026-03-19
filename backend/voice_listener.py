"""
Clarity+ Backend Voice Listener
================================
Mac-first voice pipeline:
- Porcupine wake word (via RealtimeSTT)
- Speech capture + VAD (RealtimeSTT)
- Transcription using mlx-whisper (`mlx-community/whisper-large-v3-turbo` by default)
- Backend orchestration + TTS + WebSocket state updates

Runs as a background thread started from `backend/main.py` lifespan.
"""

import asyncio
import logging
import queue
import re
import threading
import tempfile
import wave
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TTS Helper (pyttsx3)
# ---------------------------------------------------------------------------
_tts_engine = None
_tts_lock = threading.Lock()
_tts_imported = False


def _ensure_tts():
    global _tts_imported
    if _tts_imported:
        return
    import pyttsx3  # noqa: F401

    _tts_imported = True


def _speak(text: str):
    """Speak text using pyttsx3 (blocking, thread-safe)."""
    if not text:
        return
    try:
        global _tts_engine
        with _tts_lock:
            if not _tts_imported:
                _ensure_tts()
            if _tts_engine is None:
                import pyttsx3 as _pyttsx3

                _tts_engine = _pyttsx3.init()
                _tts_engine.setProperty("rate", 175)
            _tts_engine.say(text)
            _tts_engine.runAndWait()
    except Exception as e:
        logger.error(f"TTS error: {e}")


def _strip_wake_word(text: str) -> str:
    """
    Remove the configured wake word from the beginning of Whisper output.
    Porcupine detects the wake word, but Whisper may still include it in some cases.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned

    lower = cleaned.lower()

    # Historical UI wording.
    lower = re.sub(r"^hey\s+clarity\b", "", lower).strip()

    wake_words = [w.strip().lower() for w in (settings.WAKE_WORDS or "").split(",") if w.strip()]
    for w in wake_words:
        w_esc = re.escape(w)
        lower = re.sub(rf"^({w_esc})(\b[\s,:-]*)", "", lower).strip()
        lower = re.sub(rf"^({w_esc})\b", "", lower).strip()

    return lower


class VoiceListener:
    """
    Background voice listener that:
    1. Uses RealtimeSTT with Porcupine for wake-word detection
    2. Captures a single utterance using VAD
    3. Transcribes using mlx-whisper
    4. Sends transcript through `voice_orchestrator.process_voice_intent()`
    5. Speaks assistant response via pyttsx3
    6. Pushes voice state updates over WebSocket
    """

    def __init__(self, ws_manager, event_loop: asyncio.AbstractEventLoop):
        self._manager = ws_manager
        self._loop = event_loop
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._trigger_queue: queue.Queue[bool] = queue.Queue()
        self._recorder = None
        self._recorder_lock = threading.Lock()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="voice-listener")
        self._thread.start()
        logger.info("Voice listener started")

    def stop(self):
        self._running = False
        with self._recorder_lock:
            try:
                if self._recorder is not None:
                    self._recorder.shutdown()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("Voice listener stopped")

    def trigger_listen(self):
        """
        Skip wake word and capture the next utterance (space bar / UI testing).
        """
        try:
            self._trigger_queue.put_nowait(True)
        except queue.Full:
            pass

        # If the recorder is already live, start recording immediately.
        with self._recorder_lock:
            try:
                if self._recorder is not None and not getattr(self._recorder, "is_recording", False):
                    self._recorder.start()
                    self._set_state("LISTENING")
            except Exception:
                pass

    # -- WebSocket broadcast helpers (thread-safe via event loop) --

    def _broadcast(self, data: dict):
        """Schedule a WebSocket broadcast on the main asyncio loop."""
        try:
            asyncio.run_coroutine_threadsafe(self._manager.broadcast(data), self._loop)
        except Exception:
            pass

    def _set_state(self, state: str, caption: Optional[str] = None, transcript: Optional[str] = None):
        msg: dict = {"state": state}
        if caption:
            msg["caption"] = caption
        if transcript:
            msg["transcript"] = transcript
        self._broadcast(msg)

    # -- Audio -> text helpers --

    def _maybe_apply_speex_ns(self, pcm16, sample_rate: int):
        if not settings.SPEEX_NOISE_SUPPRESSION:
            return pcm16

        try:
            from speexdsp_ns import NoiseSuppression
        except Exception as e:
            logger.warning(f"Speex noise suppression requested but unavailable: {e}")
            return pcm16

        import numpy as np  # type: ignore

        target_rate = 16000
        if sample_rate != target_rate:
            # Simple resampling for the optional preprocessor.
            x = np.linspace(0.0, 1.0, num=len(pcm16), endpoint=False)
            xi = np.linspace(0.0, 1.0, num=int(len(pcm16) * target_rate / sample_rate), endpoint=False)
            pcm16 = np.interp(xi, x, pcm16).astype(np.int16)
            sample_rate = target_rate

        ns = NoiseSuppression.create(settings.SPEEX_FRAME_SIZE, sample_rate)
        frame_size = settings.SPEEX_FRAME_SIZE
        out = np.zeros_like(pcm16)

        for start in range(0, len(pcm16), frame_size):
            end = start + frame_size
            frame = pcm16[start:end]
            if len(frame) < frame_size:
                pad = np.zeros(frame_size - len(frame), dtype=np.int16)
                frame = np.concatenate([frame, pad], axis=0)
            processed_bytes = ns.process(frame.tobytes())
            processed_frame = np.frombuffer(processed_bytes, dtype=np.int16)
            out[start:end] = processed_frame[: end - start]

        return out

    def _transcribe_with_mlx(self, pcm16, sample_rate: int) -> str:
        """
        Write PCM16 to a temporary WAV file and transcribe via mlx-whisper.
        """
        import numpy as np  # type: ignore
        import mlx_whisper  # type: ignore

        pcm16 = np.asarray(pcm16, dtype=np.int16)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(int(sample_rate))
                wf.writeframes(pcm16.tobytes())

            result = mlx_whisper.transcribe(tmp.name, path_or_hf_repo=settings.WHISPER_MODEL)
            return (result.get("text") or "").strip()

    def _process_captured_audio(self, pcm16, sample_rate: int) -> Optional[str]:
        if pcm16 is None or len(pcm16) == 0:
            return None

        pcm16 = self._maybe_apply_speex_ns(pcm16, sample_rate)
        text = self._transcribe_with_mlx(pcm16, sample_rate)
        if not text:
            return None

        command = _strip_wake_word(text)
        return command or None

    # -- Main listener loop --

    def _run(self):
        try:
            from RealtimeSTT import AudioToTextRecorder  # type: ignore
        except Exception as e:
            logger.error(f"RealtimeSTT missing/unavailable; cannot start voice listener: {e}")
            return

        logger.info(
            f"Initializing voice listener (wake words={settings.WAKE_WORDS}, "
            f"wake_sensitivity={settings.WAKE_WORD_SENSITIVITY}, whisper={settings.WHISPER_MODEL})"
        )

        def _on_wakeword_detected():
            self._set_state("LISTENING")

        # Create the recorder once; we will repeatedly call wait_audio() for each utterance.
        try:
            recorder = AudioToTextRecorder(
                # RealtimeSTT will still initialize its internal faster-whisper
                # pipeline in a worker process, even though we do final STT
                # using mlx-whisper. Keep it small to minimize startup time.
                model="tiny",
                download_root=None,
                language="en",
                compute_type="default",
                use_microphone=True,
                spinner=False,
                wakeword_backend="pvporcupine",
                wake_words=settings.WAKE_WORDS,
                wake_words_sensitivity=settings.WAKE_WORD_SENSITIVITY,
                wake_word_timeout=settings.WAKE_WORD_TIMEOUT,
                silero_sensitivity=settings.SILERO_SENSITIVITY,
                webrtc_sensitivity=settings.WEBRTC_SENSITIVITY,
                post_speech_silence_duration=settings.POST_SPEECH_SILENCE_DURATION,
                silero_deactivity_detection=True,
                on_wakeword_detected=_on_wakeword_detected,
                enable_realtime_transcription=False,
                level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
            )
        except Exception as e:
            logger.error(f"Failed to initialize RealtimeSTT recorder: {e}")
            return

        with self._recorder_lock:
            self._recorder = recorder

        logger.info("Microphone listening — say wake word or use UI trigger (space bar).")

        try:
            # If a manual trigger arrived before initialization finished, honor it.
            try:
                while True:
                    self._trigger_queue.get_nowait()
                    recorder.start()
                    self._set_state("LISTENING")
            except queue.Empty:
                pass

            while self._running:
                # Blocking: wait until VAD ends the current utterance and audio is available.
                recorder.wait_audio()

                audio_float = getattr(recorder, "audio", None)
                if audio_float is None:
                    self._set_state("IDLE")
                    continue

                # RealtimeSTT stores captured audio as float in [-1, 1].
                import numpy as np  # type: ignore

                pcm16 = np.clip(
                    np.asarray(audio_float, dtype=np.float32) * 32767.0, -32768.0, 32767.0
                ).astype(np.int16)
                sample_rate = int(getattr(recorder, "sample_rate", 16000))

                command = self._process_captured_audio(pcm16, sample_rate)
                if not command:
                    self._set_state("IDLE")
                    continue

                self._process_command(command, raw_text=command)
        except Exception as e:
            logger.error(f"Voice listener loop failed: {e}")
        finally:
            with self._recorder_lock:
                try:
                    if self._recorder is not None:
                        self._recorder.shutdown()
                except Exception:
                    pass
            logger.info("Voice listener stopped.")

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
            future = asyncio.run_coroutine_threadsafe(process_voice_intent(request), self._loop)
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

