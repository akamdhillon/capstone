#!/usr/bin/env python3
"""
Clarity+ Voice Test Script (Jetson)
===================================
Run on Jetson to verify voice stack: imports, mic (Whisper STT), and speaker (pyttsx3).
Records ~5 second chunks, transcribes with Whisper, speaks back. Press Ctrl+C to exit.

  python3 test_voice_jetson.py

Dependencies: openai-whisper, sounddevice, pyttsx3, numpy
  pip install openai-whisper sounddevice pyttsx3 numpy
"""

import os
import sys
import time
from pathlib import Path

# Check imports first
def check_imports():
    errors = []
    try:
        import whisper
        print("  [OK] whisper")
    except ImportError as e:
        errors.append(f"whisper: {e}")
    try:
        import sounddevice as sd
        print("  [OK] sounddevice")
    except ImportError as e:
        errors.append(f"sounddevice: {e}")
    try:
        import pyttsx3
        print("  [OK] pyttsx3")
    except ImportError as e:
        errors.append(f"pyttsx3: {e}")
    try:
        import numpy as np
        print("  [OK] numpy")
    except ImportError as e:
        errors.append(f"numpy: {e}")
    if errors:
        print("\nMissing dependencies. Install with:")
        print("  pip install openai-whisper sounddevice pyttsx3 numpy")
        sys.exit(1)


def main():
    print("=" * 50)
    print("  Clarity+ Voice Test (Jetson)")
    print("  Say anything — it will be spoken back.")
    print("  Records ~5 sec chunks. Press Ctrl+C to quit.")
    print("=" * 50)
    print("\n1. Checking imports...")
    check_imports()

    import numpy as np
    import sounddevice as sd
    import whisper
    import pyttsx3

    # Whisper model: "tiny"=fast/light, "base"=better accuracy, "small"=slower
    model_name = os.getenv("WHISPER_MODEL", "base")
    print(f"\n2. Loading Whisper model ({model_name})...")
    stt_model = whisper.load_model(model_name, device="cpu")
    print("  [OK] Whisper ready")

    # TTS
    print("\n3. Initializing TTS (pyttsx3)...")
    engine = pyttsx3.init()
    engine.setProperty("rate", 160)
    print("  [OK] TTS ready")

    # Mic
    SAMPLE_RATE = 16000
    CHUNK_SEC = 5
    chunk_frames = SAMPLE_RATE * CHUNK_SEC
    print(f"\n4. Opening microphone ({SAMPLE_RATE} Hz, {CHUNK_SEC}s chunks)...")
    try:
        stream = sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    except Exception as e:
        print(f"  [FAIL] {e}")
        sys.exit(1)
    print("  [OK] Microphone open")

    def speak(text: str):
        if not text or not text.strip():
            return
        text = text.strip()[:300]
        print(f"  >> Speaking: {text}")
        engine.say(text)
        engine.runAndWait()

    print("\n5. Listening... Say something, then wait ~5 sec for processing.\n")
    stream.start()

    try:
        while True:
            print("  Recording...", end=" ", flush=True)
            data, _ = stream.read(chunk_frames)
            print("done. Transcribing...", end=" ", flush=True)
            # sounddevice returns a buffer; convert to numpy int16 then float32 for Whisper
            audio_i16 = np.frombuffer(data, dtype=np.int16)
            audio_f32 = audio_i16.astype(np.float32) / 32768.0
            result = stt_model.transcribe(audio_f32, fp16=False, language="en")
            text = (result.get("text") or "").strip()
            print("done.")
            if text:
                print(f"  Heard: {text}")
                speak(text)
            else:
                print("  (no speech detected)")
    except KeyboardInterrupt:
        print("\n\nStopped.")
    finally:
        stream.stop()
        stream.close()


if __name__ == "__main__":
    main()
