import os
import wave
import logging
import time
from pathlib import Path
from piper import PiperVoice

logger = logging.getLogger(__name__)

class PiperTTSService:
    def __init__(self, model_path: str = None, config_path: str = None):
        # Default paths
        base_dir = Path(__file__).resolve().parent
        self.model_path = model_path or str(base_dir / "models/piper/en_US-lessac-medium.onnx")
        self.config_path = config_path or str(base_dir / "models/piper/en_US-lessac-medium.onnx.json")
        
        # Load voice
        logger.info(f"Loading Piper voice from {self.model_path}")
        try:
            import onnxruntime as ort
            sess_options = ort.SessionOptions()
            sess_options.intra_op_num_threads = 1
            sess_options.inter_op_num_threads = 1
            sess_options.enable_mem_pattern = True
            
            # Prefer CoreML on Mac
            providers = ['CoreMLExecutionProvider', 'CPUExecutionProvider']
            
            self.voice = PiperVoice.load(
                self.model_path, 
                config_path=self.config_path,
                use_cuda=False # Not for Mac
            )
            
            # Manually update the session providers if possible, 
            # though PiperVoice.load usually handles internal init.
            # If the high-level API doesn't allow it, we'll stick to the default but optimized threads.
            
            logger.info(f"Piper voice loaded. Providers: {providers}")
        except Exception as e:
            logger.error(f"Failed to load Piper voice: {e}")
            self.voice = None

    def synthesize(self, text: str, output_path: str = "output.wav"):
        """Synthesize text to a WAV file."""
        if not self.voice:
            logger.error("TTS voice not loaded. Synthesis failed.")
            return False

        try:
            start_time = time.time()
            with wave.open(output_path, "wb") as wav_file:
                # Set WAV header parameters explicitly for Piper
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2) # 16-bit
                wav_file.setframerate(22050)
                
                for audio_chunk in self.voice.synthesize(text):
                    # Each audio_chunk represents a segment of synthesized audio
                    wav_file.writeframes(audio_chunk.audio_int16_bytes)
            
            elapsed = time.time() - start_time
            file_size = os.path.getsize(output_path)
            logger.info(f"Synthesized '{text[:20]}...' to {output_path} ({file_size} bytes) in {elapsed:.3f}s")
            return True
        except Exception as e:
            logger.error(f"Piper synthesis failed: {e}")
            return False

# Singleton instance
_instance = None

def get_tts_service():
    global _instance
    if _instance is None:
        _instance = PiperTTSService()
    return _instance
