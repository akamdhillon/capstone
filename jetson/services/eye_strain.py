"""
Clarity+ Eye Strain Service
===========================
Blink rate monitoring via Eye Aspect Ratio (EAR) and
sclera redness analysis via HSV color-space histograms.
"""

import logging
import time
from typing import Optional, Dict, Any, List, Tuple
from collections import deque
import numpy as np

from config import settings

logger = logging.getLogger("clarity-ml.eye_strain")

# Dependencies
_mediapipe = None
_cv2 = None


def _get_dependencies():
    """Lazy load dependencies."""
    global _mediapipe, _cv2
    
    if _cv2 is None:
        import cv2
        _cv2 = cv2
    
    if _mediapipe is None:
        try:
            import mediapipe as mp
            _mediapipe = mp
            logger.info("MediaPipe loaded for eye tracking")
        except ImportError as e:
            logger.warning(f"MediaPipe not available: {e}")
    
    return _cv2, _mediapipe


class EyeStrainService:
    """
    Eye Strain analysis service.
    
    Metrics:
        1. Blink Rate via Eye Aspect Ratio (EAR)
           - Normal: 15-20 blinks/minute
           - Low blink rate indicates eye strain
        
        2. Sclera Redness Analysis
           - HSV color-space histogram analysis
           - Detects redness in eye white area
    
    Uses MediaPipe Face Mesh for eye landmark detection.
    """
    
    # EAR thresholds
    EAR_THRESHOLD = 0.21       # Below this = eyes closed (blink)
    EAR_CONSEC_FRAMES = 2      # Frames below threshold to count as blink
    
    # Normal blink rate range (blinks per minute)
    NORMAL_BLINK_RATE_MIN = 15
    NORMAL_BLINK_RATE_MAX = 20
    
    # Eye landmark indices for Face Mesh (468 landmarks total)
    # Left eye landmarks
    LEFT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
    # Right eye landmarks  
    RIGHT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
    
    # Sclera (eye white) approximate regions
    LEFT_SCLERA_INDICES = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
    RIGHT_SCLERA_INDICES = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
    
    def __init__(self):
        self._face_mesh = None
        self._initialized = False
        
        # Blink detection state
        self._blink_counter = 0
        self._frame_counter = 0
        self._ear_below_threshold_frames = 0
        
        # Blink rate tracking (rolling window)
        self._blink_timestamps: deque = deque(maxlen=100)
        self._analysis_start_time: float = 0.0
        
        # Performance tracking
        self._last_inference_time_ms: float = 0.0
    
    def initialize(self) -> bool:
        """Initialize MediaPipe Face Mesh for eye tracking."""
        cv2, mp = _get_dependencies()
        
        if mp is None:
            logger.error("Cannot initialize: MediaPipe not available")
            return False
        
        try:
            mp_face_mesh = mp.solutions.face_mesh
            
            self._face_mesh = mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,  # Enables iris landmarks
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            
            self._analysis_start_time = time.time()
            self._initialized = True
            logger.info("Eye strain service initialized (MediaPipe Face Mesh)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Face Mesh: {e}")
            return False
    
    def _calculate_ear(self, eye_landmarks: List[Tuple[float, float]]) -> float:
        """
        Calculate Eye Aspect Ratio (EAR).
        
        EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
        
        Where p1-p6 are the 6 eye landmark points:
            p1: outer corner
            p2: upper outer
            p3: upper inner
            p4: inner corner
            p5: lower inner
            p6: lower outer
        """
        if len(eye_landmarks) != 6:
            return 0.0
        
        # Vertical distances
        v1 = np.linalg.norm(np.array(eye_landmarks[1]) - np.array(eye_landmarks[5]))
        v2 = np.linalg.norm(np.array(eye_landmarks[2]) - np.array(eye_landmarks[4]))
        
        # Horizontal distance
        h = np.linalg.norm(np.array(eye_landmarks[0]) - np.array(eye_landmarks[3]))
        
        if h == 0:
            return 0.0
        
        ear = (v1 + v2) / (2.0 * h)
        return ear
    
    def _get_eye_landmarks(self, face_landmarks, indices: List[int], width: int, height: int) -> List[Tuple[float, float]]:
        """Extract eye landmarks as pixel coordinates."""
        landmarks = []
        for idx in indices:
            lm = face_landmarks.landmark[idx]
            landmarks.append((lm.x * width, lm.y * height))
        return landmarks
    
    def _analyze_sclera_redness(
        self,
        image: np.ndarray,
        face_landmarks,
        indices: List[int],
        width: int,
        height: int
    ) -> Dict[str, float]:
        """
        Analyze sclera (eye white) redness using HSV histogram.
        
        Returns redness score (0-100) where higher = more red.
        """
        cv2, _ = _get_dependencies()
        
        try:
            # Get sclera region points
            points = []
            for idx in indices:
                lm = face_landmarks.landmark[idx]
                points.append([int(lm.x * width), int(lm.y * height)])
            
            points = np.array(points, dtype=np.int32)
            
            # Create mask for sclera region
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.fillPoly(mask, [points], 255)
            
            # Convert to HSV
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # Extract region
            sclera_hsv = cv2.bitwise_and(hsv, hsv, mask=mask)
            
            # Analyze red channel in sclera region
            # Red in HSV: H is around 0-10 or 170-180
            h_channel = sclera_hsv[:, :, 0]
            s_channel = sclera_hsv[:, :, 1]
            
            # Find pixels in mask
            mask_pixels = mask > 0
            if np.sum(mask_pixels) == 0:
                return {"redness_score": 0.0, "pixels_analyzed": 0}
            
            h_values = h_channel[mask_pixels]
            s_values = s_channel[mask_pixels]
            
            # Count red-ish pixels (low H with decent saturation)
            red_low = (h_values < 15) & (s_values > 30)
            red_high = (h_values > 165) & (s_values > 30)
            red_pixels = np.sum(red_low | red_high)
            
            total_pixels = len(h_values)
            redness_ratio = red_pixels / total_pixels if total_pixels > 0 else 0
            
            # Convert to 0-100 score
            redness_score = min(100.0, redness_ratio * 500)  # Scale factor
            
            return {
                "redness_score": round(redness_score, 2),
                "pixels_analyzed": total_pixels,
                "red_pixel_ratio": round(redness_ratio, 4)
            }
            
        except Exception as e:
            logger.error(f"Sclera analysis failed: {e}")
            return {"redness_score": 0.0, "error": str(e)}
    
    def _update_blink_count(self, ear: float) -> bool:
        """
        Update blink detection state based on EAR.
        
        Returns True if a blink was just detected.
        """
        blink_detected = False
        
        if ear < self.EAR_THRESHOLD:
            self._ear_below_threshold_frames += 1
        else:
            if self._ear_below_threshold_frames >= self.EAR_CONSEC_FRAMES:
                # Blink completed
                self._blink_counter += 1
                self._blink_timestamps.append(time.time())
                blink_detected = True
            
            self._ear_below_threshold_frames = 0
        
        self._frame_counter += 1
        return blink_detected
    
    def _calculate_blink_rate(self) -> float:
        """Calculate blinks per minute from recent data."""
        if len(self._blink_timestamps) < 2:
            return 0.0
        
        current_time = time.time()
        
        # Count blinks in last 60 seconds
        one_minute_ago = current_time - 60
        recent_blinks = [t for t in self._blink_timestamps if t > one_minute_ago]
        
        return float(len(recent_blinks))
    
    def analyze(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Analyze eye strain metrics in an image.
        
        Args:
            image: BGR image as numpy array
        
        Returns:
            Dict with EAR, blink rate, and redness analysis
        """
        if not self._initialized:
            self.initialize()
        
        cv2, mp = _get_dependencies()
        
        if self._face_mesh is None:
            return {"error": "Face Mesh not initialized", "face_detected": False}
        
        start_time = time.time()
        
        try:
            # Get image dimensions
            height, width = image.shape[:2]
            
            # Convert to RGB for MediaPipe
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Process image
            results = self._face_mesh.process(rgb_image)
            
            self._last_inference_time_ms = (time.time() - start_time) * 1000
            
            if not results.multi_face_landmarks:
                return {
                    "face_detected": False,
                    "message": "No face detected",
                    "inference_time_ms": self._last_inference_time_ms
                }
            
            face_landmarks = results.multi_face_landmarks[0]
            
            # Get eye landmarks
            left_eye = self._get_eye_landmarks(face_landmarks, self.LEFT_EYE_INDICES, width, height)
            right_eye = self._get_eye_landmarks(face_landmarks, self.RIGHT_EYE_INDICES, width, height)
            
            # Calculate EAR for both eyes
            left_ear = self._calculate_ear(left_eye)
            right_ear = self._calculate_ear(right_eye)
            avg_ear = (left_ear + right_ear) / 2.0
            
            # Update blink detection
            blink_detected = self._update_blink_count(avg_ear)
            
            # Calculate blink rate
            blink_rate = self._calculate_blink_rate()
            
            # Analyze sclera redness
            left_redness = self._analyze_sclera_redness(
                image, face_landmarks, self.LEFT_SCLERA_INDICES, width, height
            )
            right_redness = self._analyze_sclera_redness(
                image, face_landmarks, self.RIGHT_SCLERA_INDICES, width, height
            )
            
            avg_redness = (left_redness.get("redness_score", 0) + right_redness.get("redness_score", 0)) / 2
            
            # Determine eye strain indicators
            low_blink_rate = blink_rate < self.NORMAL_BLINK_RATE_MIN if blink_rate > 0 else False
            high_redness = avg_redness > 30.0  # Threshold for concern
            
            # Calculate strain score (0-100, higher = more strain)
            strain_score = 0.0
            if blink_rate > 0:
                # Low blink rate contributes to strain
                if blink_rate < self.NORMAL_BLINK_RATE_MIN:
                    strain_score += (self.NORMAL_BLINK_RATE_MIN - blink_rate) * 4
            strain_score += avg_redness * 0.5  # Redness contribution
            strain_score = min(100.0, strain_score)
            
            result = {
                "face_detected": True,
                "eye_aspect_ratio": {
                    "left": round(left_ear, 4),
                    "right": round(right_ear, 4),
                    "average": round(avg_ear, 4),
                    "threshold": self.EAR_THRESHOLD
                },
                "blink_analysis": {
                    "blink_detected": blink_detected,
                    "total_blinks": self._blink_counter,
                    "blink_rate_per_minute": round(blink_rate, 1),
                    "is_low": low_blink_rate,
                    "normal_range": f"{self.NORMAL_BLINK_RATE_MIN}-{self.NORMAL_BLINK_RATE_MAX}"
                },
                "redness_analysis": {
                    "left_eye": left_redness,
                    "right_eye": right_redness,
                    "average_score": round(avg_redness, 2),
                    "is_elevated": high_redness
                },
                "strain_score": round(strain_score, 1),
                "strain_level": self._get_strain_level(strain_score),
                "inference_time_ms": self._last_inference_time_ms
            }
            
            logger.debug(f"Eye strain: score={strain_score:.1f}, blinks={blink_rate:.1f}/min")
            
            return result
            
        except Exception as e:
            logger.error(f"Eye strain analysis failed: {e}")
            return {"error": str(e), "face_detected": False}
    
    def _get_strain_level(self, score: float) -> str:
        """Convert strain score to human-readable level."""
        if score < 20:
            return "low"
        elif score < 50:
            return "moderate"
        elif score < 75:
            return "high"
        else:
            return "severe"
    
    def reset_blink_counter(self):
        """Reset blink tracking for new session."""
        self._blink_counter = 0
        self._frame_counter = 0
        self._ear_below_threshold_frames = 0
        self._blink_timestamps.clear()
        self._analysis_start_time = time.time()
        logger.info("Blink counter reset")
    
    def cleanup(self):
        """Release resources."""
        if self._face_mesh:
            self._face_mesh.close()
            self._face_mesh = None
        self._initialized = False
        logger.info("Eye strain service cleaned up")
    
    @property
    def last_inference_time_ms(self) -> float:
        """Get the last inference time in milliseconds."""
        return self._last_inference_time_ms
    
    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
