import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from voice_tts import get_tts_service
import pygame
import time

def test_tts():
    print("Initializing TTS Service...")
    tts = get_tts_service()
    
    test_text = "Welcome to Clarity plus. Your local text to speech is now active and faster than ever."
    output_wav = "test_piper.wav"
    
    print(f"Synthesizing: '{test_text}'")
    success = tts.synthesize(test_text, output_wav)
    
    if success:
        print(f"✓ Synthesis successful! Saved to {output_wav}")
        print("Initializing Pygame mixer for playback...")
        pygame.mixer.init()
        try:
            sound = pygame.mixer.Sound(output_wav)
            print("Playing audio...")
            sound.play()
            while pygame.mixer.get_busy():
                time.sleep(0.1)
            print("✓ Playback finished.")
        except Exception as e:
            print(f"✗ Playback failed: {e}")
    else:
        print("✗ Synthesis failed.")

if __name__ == "__main__":
    test_tts()
