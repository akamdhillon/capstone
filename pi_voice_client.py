import os
import time
import math
import base64
import requests
import json
import logging
from typing import Optional
import cv2

from dotenv import load_dotenv
import pvporcupine
from pvrecorder import PvRecorder
import whisper
import httpx
from voice_tts import get_tts_service
import pygame

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_singleton():
    """Ensure only one instance of the voice client is running."""
    import socket
    try:
        # Bind to a local port. If it fails, another instance is running.
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 9999))
        # Keep the socket open to hold the lock
        return lock_socket
    except socket.error:
        print("\n[ERROR] Another instance of pi_voice_client.py is already running.")
        print("Please close the other process first to avoid overlapping audio and conflicts.\n")
        import sys
        sys.exit(1)

# Global singleton lock
_singleton_lock = ensure_singleton()

# Config
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000/voice/intent")
BACKEND_FACE_URL = os.environ.get("BACKEND_FACE_URL", "http://localhost:8000/api/face/recognize")
FACE_CONFIDENCE_THRESHOLD = 0.6  # Akam's suggested threshold


# Initialize local TTS
tts = get_tts_service()
pygame.mixer.init()

# Initialize whisper model (tiny is faster for Raspberry Pi)
stt_model = whisper.load_model("tiny")

# --- Global State ---
VOICE_HISTORY = []

def report_status(state: str, user_id: Optional[str] = None, display_name: Optional[str] = None):
    """Report current state to the backend for frontend sync."""
    try:
        url = "http://localhost:8000/api/voice/status"
        payload = {
            "state": state,
            "user_id": user_id if user_id else "guest",
            "display_name": display_name if display_name else "Guest"
        }
        httpx.post(url, json=payload, timeout=2.0)
    except Exception as e:
        logger.debug(f"Failed to report status: {e}")

def capture_and_recognize() -> tuple[str, str]:
    """Capture a camera frame and identify the user via face recognition.
    Returns (user_id, display_name).
    """
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.warning("Camera not available, treating as guest.")
            return "guest", "Guest"
        
        # Let the camera warm up
        time.sleep(0.5)
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            logger.warning("Failed to capture frame, treating as guest.")
            return "guest", "Guest"
        
        # Encode frame to base64 JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        b64_image = base64.b64encode(buffer).decode('utf-8')
        
        # Send to backend face recognition
        logger.info("Identifying user via face recognition...")
        res = requests.post(BACKEND_FACE_URL, json={"image": b64_image}, timeout=10.0)
        
        if res.status_code == 200:
            data = res.json()
            if data.get("match"):
                name = data.get("name", "Guest")
                user_id = data.get("user_id", "guest")
                confidence = data.get("confidence", 0)
                
                if confidence >= FACE_CONFIDENCE_THRESHOLD:
                    logger.info(f"Face recognized: {name} (confidence: {confidence:.2f})")
                    return user_id, name
                else:
                    logger.info(f"Face matched {name} but confidence {confidence:.2f} < {FACE_CONFIDENCE_THRESHOLD}. Treating as Guest.")
                    return "guest", "Guest"
            else:
                match_type = data.get("match_type", "unknown")
                logger.info(f"Face not recognized (type: {match_type}). Treating as Guest.")
                return "guest", "Guest"
        else:
            logger.warning(f"Face service returned {res.status_code}")
            return "guest", "Guest"
            
    except Exception as e:
        logger.debug(f"Face recognition failed: {e}")
        return "guest", "Guest"

def record_audio(sample_rate=16000, silence_threshold=500, silence_duration=1.5, max_duration=30) -> str:
    """Record audio until the user stops talking (VAD-based).
    
    Args:
        sample_rate: Audio sample rate in Hz.
        silence_threshold: RMS energy below this = silence.
        silence_duration: Seconds of continuous silence to stop recording.
        max_duration: Maximum recording time in seconds (safety cap).
    """
    logger.info("Recording... (speak now, will stop on silence)")
    recorder = PvRecorder(device_index=-1, frame_length=512)
    recorder.start()
    
    audio_data = []
    silent_frames = 0
    frames_for_silence = int((sample_rate * silence_duration) / 512)
    max_frames = int((sample_rate * max_duration) / 512)
    total_frames = 0
    has_speech = False
    
    # Skip the first ~0.3s to avoid wake word bleed
    warmup_frames = int((sample_rate * 0.3) / 512)
    
    try:
        for _ in range(warmup_frames):
            recorder.read()  # discard warmup frames
        
        while total_frames < max_frames:
            frame = recorder.read()
            audio_data.extend(frame)
            total_frames += 1
            
            # Calculate RMS energy of this frame
            rms = math.sqrt(sum(s * s for s in frame) / len(frame))
            
            if rms > silence_threshold:
                silent_frames = 0
                has_speech = True
            else:
                silent_frames += 1
            
            # Only stop on silence AFTER we've detected speech
            if has_speech and silent_frames >= frames_for_silence:
                logger.info(f"Silence detected after {total_frames * 512 / sample_rate:.1f}s - stopping.")
                break
    finally:
        recorder.stop()
        recorder.delete()
    
    duration = total_frames * 512 / sample_rate
    logger.info(f"Recorded {duration:.1f}s of audio.")
        
    import wave
    import struct
    temp_wav = "temp_voice.wav"
    with wave.open(temp_wav, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(struct.pack('h' * len(audio_data), *audio_data))
        
    return temp_wav

def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using Whisper."""
    result = stt_model.transcribe(audio_path, language='en')
    text = result["text"].strip()
    return text

def query_voice_orchestrator(text: str, user_id: str, display_name: str, history: list) -> dict:
    """Send text and history to FastAPI LLM route."""
    payload = {
        "user_text": text,
        "user_id": user_id,
        "display_name": display_name,
        "history": history
    }
    logger.info("Sending to voice orchestrator...")
    res = requests.post(BACKEND_URL, json=payload)
    res.raise_for_status()
    return res.json()

def play_tts(text: str):
    """Generate and play TTS using local Piper engine."""
    logger.info(f"Generating local TTS for: {text[:30]}...")
    temp_wav = "temp_response.wav"
    try:
        pygame.mixer.stop() # Stop any current playback
        if tts.synthesize(text, temp_wav):
            sound = pygame.mixer.Sound(temp_wav)
            sound.play()
            # Wait for audio to finish playing
            while pygame.mixer.get_busy():
                pygame.time.Clock().tick(10)
        else:
            logger.error("Local TTS synthesis failed.")
    except Exception as e:
        logger.error(f"TTS playback failed: {e}")

def main():
    logger.info("Starting Clarity+ Voice Client...")
    
    # Initialize Porcupine wake word engine
    # NOTE: You need a Picovoice Access Key to use Porcupine in production
    # os.environ.get("PICOVOICE_ACCESS_KEY")
    access_key = os.environ.get("PICOVOICE_ACCESS_KEY")
    if not access_key:
         logger.warning("No PICOVOICE_ACCESS_KEY found. Wake word might fail!")
         
    try:
        # Using 'bumblebee' for Mac testing; comment out Pi specific .ppn
        # keyword_path = "Hey-Clarity_en_raspberry-pi_v4_0_0.ppn"
        # porcupine = pvporcupine.create(access_key=access_key, keyword_paths=[keyword_path])
        porcupine = pvporcupine.create(access_key=access_key, keywords=['bumblebee'])
        logger.info("Loaded wake word: 'bumblebee' (Mac Test Mode)")
    except Exception as e:
        logger.error(f"Failed to load Porcupine: {e}")
        return

    recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
    recorder.start()
    
    logger.info("Listening for wake word...")
    
    last_state = None
    last_user_id = None
    last_auth_time = 0
    AUTH_TIMEOUT = 300  # 5 minutes
    
    try:
        while True:
            global VOICE_HISTORY
            if last_state != "IDLE":
                report_status("IDLE")
                last_state = "IDLE"
                
            pcm = recorder.read()
            keyword_index = porcupine.process(pcm)
            
            if keyword_index >= 0:
                logger.info("\n=== WAKE WORD DETECTED ===")
                current_time = time.time()
                
                if last_state != "LISTENING":
                    report_status("LISTENING")
                    last_state = "LISTENING"
                
                # 1. Identify User via camera
                user_id, display_name = capture_and_recognize()
                
                if user_id == "guest":
                    # Not recognized or low confidence - greet and ask to enroll
                    logger.info("User treated as guest.")
                    play_tts("I don't recognize you. Please enroll first using the mirror display.")
                    report_status("IDLE", "guest", "Guest")
                    last_state = "IDLE"
                    logger.info("Resuming wake word listening...")
                    continue
                
                logger.info(f"Identified user: {display_name} ({user_id})")
                
                # Greet the user (short vs verbose based on session cache)
                report_status("SPEAKING", user_id, display_name)
                last_state = "SPEAKING"
                
                if user_id == last_user_id and (current_time - last_auth_time) < AUTH_TIMEOUT:
                    # Already logged in recently
                    play_tts("Yes?")
                else:
                    # New session
                    play_tts(f"Hey {display_name}.")
                
                # Update session cache
                last_user_id = user_id
                last_auth_time = current_time
                
                # Now listen for their actual command
                report_status("LISTENING", user_id, display_name)
                last_state = "LISTENING"
                
                # 2. Record intent
                print("\n>>> CLARITY+ IS LISTENING... SPEAK NOW! <<<")
                audio_file = record_audio()
                
                # 3. STT
                report_status("PROCESSING", user_id, display_name)
                last_state = "PROCESSING"
                text = transcribe_audio(audio_file)
                
                if text.strip():
                    logger.info(f"User speaking: '{text}'")
                    
                    # 4. Request orchestrator (with history)
                    try:
                        response = query_voice_orchestrator(text, user_id, display_name, VOICE_HISTORY)
                        assistant_msg = response.get("assistant_message", "I didn't quite catch that.")
                        logger.info(f"Clarity+: {assistant_msg}")
                        
                        # Update local history
                        VOICE_HISTORY.append({"role": "user", "content": text})
                        VOICE_HISTORY.append({"role": "assistant", "content": assistant_msg})
                        # Keep last 10 messages
                        if len(VOICE_HISTORY) > 10:
                            VOICE_HISTORY = VOICE_HISTORY[-10:]
                        
                        # 5. TTS
                        report_status("SPEAKING", user_id, display_name)
                        last_state = "SPEAKING"
                        play_tts(assistant_msg)
                    except Exception as e:
                        logger.error(f"Orchestrator pipeline failed: {e}")
                else:
                    logger.info("No audio detected.")
                
                # Clean up
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                
                # --- NEW: Follow-up Window (Continuous Listening) ---
                follow_up_count = 0
                while follow_up_count < 2 and text.strip(): # Only follow up if something was said
                    time.sleep(0.5) # Let audio settle to avoid self-echo
                    logger.info(f"Checking for follow-up (Attempt {follow_up_count + 1})...")
                    # In a real app, you might check response.get("follow_up_needed")
                    # For now, let's just listen for a short window (5-7 seconds)
                    
                    # Subtle ping or indicator here
                    report_status("LISTENING", user_id, display_name)
                    print("\n>>> CLARITY+ IS STILL LISTENING... <<<")
                    
                    # Record with a shorter silence timeout for follow-ups
                    follow_up_audio = record_audio(silence_duration=1.2, max_duration=10)
                    text = transcribe_audio(follow_up_audio)
                    
                    if os.path.exists(follow_up_audio):
                        os.remove(follow_up_audio)
                        
                    if text.strip() and len(text.split()) > 1: # Basic check to avoid noise
                        logger.info(f"Follow-up detected: '{text}'")
                        report_status("PROCESSING", user_id, display_name)
                        try:
                            response = query_voice_orchestrator(text, user_id, display_name, VOICE_HISTORY)
                            assistant_msg = response.get("assistant_message", "Okay.")
                            logger.info(f"Clarity+: {assistant_msg}")
                            
                            VOICE_HISTORY.append({"role": "user", "content": text})
                            VOICE_HISTORY.append({"role": "assistant", "content": assistant_msg})
                            
                            report_status("SPEAKING", user_id, display_name)
                            play_tts(assistant_msg)
                            follow_up_count += 1
                        except Exception as e:
                            logger.error(f"Follow-up processing failed: {e}")
                            break
                    else:
                        logger.info("No follow-up speech detected. Ending window.")
                        break
                # --- End Follow-up ---
                    
                logger.info("Resuming wake word listening...")
                # Normal loop will reset state to IDLE
                
    except KeyboardInterrupt:
        logger.info("Stopping Voice Client...")
    finally:
        recorder.delete()
        porcupine.delete()

if __name__ == "__main__":
    main()
