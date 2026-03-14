#!/usr/bin/env python3
"""
Clarity+ Voice Test Script (Jetson)
===================================
Run on Jetson to verify voice stack: imports, mic (Vosk STT), and speaker (pyttsx3).
Continuously listens, prints and speaks whatever you say. Press Ctrl+C to exit.

  python3 test_voice_jetson.py

Dependencies: vosk, sounddevice, pyttsx3, numpy
  pip install vosk sounddevice pyttsx3 numpy
"""

import json
import os
import sys
import time
from pathlib import Path

# Check imports first
def check_imports():
    errors = []
    try:
        import vosk
        print("  [OK] vosk")
    except ImportError as e:
        errors.append(f"vosk: {e}")
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
        print("  pip install vosk sounddevice pyttsx3 numpy")
        sys.exit(1)

def main():
    print("=" * 50)
    print("  Clarity+ Voice Test (Jetson)")
    print("  Say anything — it will be spoken back.")
    print("  Press Ctrl+C to quit.")
    print("=" * 50)
    print("\n1. Checking imports...")
    check_imports()

    import numpy as np
    import sounddevice as sd
    import vosk
    import pyttsx3

    # Model (check voice service first, then script dir)
    script_dir = Path(__file__).resolve().parent
    voice_model = script_dir.parent / "services" / "voice" / "vosk-model"
    model_dir = voice_model if voice_model.exists() else script_dir / "vosk-model"
    if not model_dir.exists():
        alt = script_dir / "vosk-model-small-en-us-0.15"
        if alt.exists():
            model_dir = alt
        else:
            print("\n2. Downloading Vosk model (small English)...")
            import urllib.request
            import zipfile
            url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
            zip_file = script_dir / "vosk-model-small-en-us-0.15.zip"
            urllib.request.urlretrieve(url, zip_file)
            with zipfile.ZipFile(zip_file, "r") as zf:
                zf.extractall(script_dir)
            zip_file.unlink()
            model_dir = script_dir / "vosk-model-small-en-us-0.15"
    if not model_dir.exists():
        print(f"  [FAIL] Model not found at {model_dir}")
        sys.exit(1)
    print(f"  [OK] Vosk model: {model_dir}")

    vosk.SetLogLevel(-1)
    model = vosk.Model(str(model_dir))
    recognizer = vosk.KaldiRecognizer(model, 16000)

    # TTS
    print("\n3. Initializing TTS (pyttsx3)...")
    engine = pyttsx3.init()
    engine.setProperty("rate", 160)
    print("  [OK] TTS ready")

    # Mic
    SAMPLE_RATE = 16000
    BLOCK_MS = 200
    block_frames = int(SAMPLE_RATE * BLOCK_MS / 1000)
    print(f"\n4. Opening microphone ({SAMPLE_RATE} Hz)...")
    try:
        stream = sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=block_frames,
                                  dtype="int16", channels=1)
    except Exception as e:
        print(f"  [FAIL] {e}")
        sys.exit(1)
    print("  [OK] Microphone open")

    def speak(text: str):
        if not text or not text.strip():
            return
        text = text.strip()[:200]  # limit length
        print(f"  >> Speaking: {text}")
        engine.say(text)
        engine.runAndWait()

    print("\n5. Listening... Say something!\n")
    stream.start()

    try:
        while True:
            data, _ = stream.read(block_frames)
            data_bytes = bytes(data)
            if recognizer.AcceptWaveform(data_bytes):
                result = json.loads(recognizer.Result())
                text = (result.get("text") or "").strip()
                if text:
                    print(f"  Heard: {text}")
                    speak(text)
    except KeyboardInterrupt:
        print("\n\nStopped.")
    finally:
        stream.stop()
        stream.close()

if __name__ == "__main__":
    main()
