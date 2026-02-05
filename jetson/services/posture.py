"""
Clarity+ Posture Service
========================
MediaPipe Pose (BlazePose GHUM) for posture analysis.
Calculates head-forward angle and slouch detection.
"""

import logging
import time
import math
from typing import Optional, Dict, Any, List, Tuple
import numpy as np

from config import settings

logger = logging.getLogger("clarity-ml.posture")

# MediaPipe lazy import
_mediapipe = None


def _get_mediapipe():
    """Lazy load MediaPipe."""
    global _mediapipe
    if _mediapipe is None:
        try:
            import mediapipe as mp
            _mediapipe = mp
            logger.info("MediaPipe loaded successfully")
        except ImportError as e:
            logger.warning(f"MediaPipe not available: {e}")
    return _mediapipe


class PostureService:
    """
    Posture analysis service using MediaPipe Pose.
    
    Features:
        - 33 body keypoint detection (BlazePose GHUM)
        - Head-forward angle calculation
        - Slouch detection (thoracic kyphosis measurement)
        - Real-time posture scoring
    
    # -------------------------------------------------------------------------
    # TODO: Future MediaPipe Hands Integration
    # -------------------------------------------------------------------------
    # Placeholder for gesture control features:
    #   - Hand detection and tracking
    #   - Gesture recognition (swipe, pinch, point)
    #   - UI control via hand gestures
    #
    # Implementation notes:
    #   - Use mp.solutions.hands with max_num_hands=2
    #   - Track 21 hand landmarks per hand
    #   - Gesture state machine for UI navigation
    #
    # Example:
    #   self.hands = mp.solutions.hands.Hands(
    #       static_image_mode=False,
    #       max_num_hands=2,
    #       min_detection_confidence=0.7,
    #       min_tracking_confidence=0.5
    #   )
    # -------------------------------------------------------------------------
    """
    
    # Pose landmark indices (MediaPipe)
    NOSE = 0
    LEFT_EYE = 2
    RIGHT_EYE = 5
    LEFT_EAR = 7
    RIGHT_EAR = 8
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    
    # Posture thresholds
    HEAD_FORWARD_THRESHOLD_DEG = 15.0  # Degrees forward from vertical
    SLOUCH_THRESHOLD_DEG = 20.0        # Thoracic angle threshold
    
    def __init__(self):
        self._pose = None
        self._mp_pose = None
        self._mp_drawing = None
        self._initialized = False
        
        # Performance tracking
        self._last_inference_time_ms: float = 0.0
    
    def initialize(self) -> bool:
        """Initialize MediaPipe Pose model."""
        mp = _get_mediapipe()
        
        if mp is None:
            logger.error("Cannot initialize: MediaPipe not available")
            return False
        
        try:
            self._mp_pose = mp.solutions.pose
            self._mp_drawing = mp.solutions.drawing_utils
            
            # Initialize Pose with optimal settings for Jetson
            self._pose = self._mp_pose.Pose(
                static_image_mode=False,
                model_complexity=1,  # 0=Lite, 1=Full, 2=Heavy
                smooth_landmarks=True,
                enable_segmentation=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            
            self._initialized = True
            logger.info("MediaPipe Pose initialized (BlazePose GHUM)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MediaPipe Pose: {e}")
            return False
    
    def _extract_landmarks(self, results) -> Optional[Dict[str, Tuple[float, float, float]]]:
        """Extract relevant landmarks from MediaPipe results."""
        if not results.pose_landmarks:
            return None
        
        landmarks = results.pose_landmarks.landmark
        
        return {
            "nose": (landmarks[self.NOSE].x, landmarks[self.NOSE].y, landmarks[self.NOSE].z),
            "left_eye": (landmarks[self.LEFT_EYE].x, landmarks[self.LEFT_EYE].y, landmarks[self.LEFT_EYE].z),
            "right_eye": (landmarks[self.RIGHT_EYE].x, landmarks[self.RIGHT_EYE].y, landmarks[self.RIGHT_EYE].z),
            "left_ear": (landmarks[self.LEFT_EAR].x, landmarks[self.LEFT_EAR].y, landmarks[self.LEFT_EAR].z),
            "right_ear": (landmarks[self.RIGHT_EAR].x, landmarks[self.RIGHT_EAR].y, landmarks[self.RIGHT_EAR].z),
            "left_shoulder": (landmarks[self.LEFT_SHOULDER].x, landmarks[self.LEFT_SHOULDER].y, landmarks[self.LEFT_SHOULDER].z),
            "right_shoulder": (landmarks[self.RIGHT_SHOULDER].x, landmarks[self.RIGHT_SHOULDER].y, landmarks[self.RIGHT_SHOULDER].z),
            "left_hip": (landmarks[self.LEFT_HIP].x, landmarks[self.LEFT_HIP].y, landmarks[self.LEFT_HIP].z),
            "right_hip": (landmarks[self.RIGHT_HIP].x, landmarks[self.RIGHT_HIP].y, landmarks[self.RIGHT_HIP].z),
        }
    
    def _calculate_head_forward_angle(self, landmarks: Dict) -> float:
        """
        Calculate head-forward angle from vertical.
        
        Uses ear-to-shoulder relationship to determine forward head posture.
        Positive angle = head forward (bad posture)
        """
        # Midpoint of ears
        ear_mid_x = (landmarks["left_ear"][0] + landmarks["right_ear"][0]) / 2
        ear_mid_y = (landmarks["left_ear"][1] + landmarks["right_ear"][1]) / 2
        
        # Midpoint of shoulders
        shoulder_mid_x = (landmarks["left_shoulder"][0] + landmarks["right_shoulder"][0]) / 2
        shoulder_mid_y = (landmarks["left_shoulder"][1] + landmarks["right_shoulder"][1]) / 2
        
        # Calculate angle from vertical
        dx = ear_mid_x - shoulder_mid_x
        dy = ear_mid_y - shoulder_mid_y
        
        # Angle in degrees (0 = perfect vertical alignment)
        angle_rad = math.atan2(dx, -dy)  # Negative dy because y increases downward
        angle_deg = math.degrees(angle_rad)
        
        return angle_deg
    
    def _calculate_slouch_angle(self, landmarks: Dict) -> float:
        """
        Calculate slouch angle (thoracic kyphosis indicator).
        
        Measures the angle of the spine from shoulders to hips.
        Higher angle = more slouching.
        """
        # Shoulder midpoint
        shoulder_mid_x = (landmarks["left_shoulder"][0] + landmarks["right_shoulder"][0]) / 2
        shoulder_mid_y = (landmarks["left_shoulder"][1] + landmarks["right_shoulder"][1]) / 2
        
        # Hip midpoint
        hip_mid_x = (landmarks["left_hip"][0] + landmarks["right_hip"][0]) / 2
        hip_mid_y = (landmarks["left_hip"][1] + landmarks["right_hip"][1]) / 2
        
        # Ideal vertical line vs actual spine line
        dx = shoulder_mid_x - hip_mid_x
        dy = shoulder_mid_y - hip_mid_y
        
        # Angle deviation from vertical
        angle_rad = math.atan2(abs(dx), abs(dy))
        angle_deg = math.degrees(angle_rad)
        
        return angle_deg
    
    def _calculate_shoulder_alignment(self, landmarks: Dict) -> Dict[str, Any]:
        """Calculate shoulder alignment metrics."""
        left_y = landmarks["left_shoulder"][1]
        right_y = landmarks["right_shoulder"][1]
        
        # Height difference (normalized)
        height_diff = abs(left_y - right_y)
        
        # Determine which shoulder is higher
        if left_y < right_y:
            higher_shoulder = "left"
        elif right_y < left_y:
            higher_shoulder = "right"
        else:
            higher_shoulder = "level"
        
        return {
            "height_difference": height_diff,
            "higher_shoulder": higher_shoulder,
            "is_level": height_diff < 0.02  # 2% threshold
        }
    
    def analyze(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Analyze posture in an image.
        
        Args:
            image: BGR image as numpy array
        
        Returns:
            Dict with posture analysis results
        """
        if not self._initialized:
            self.initialize()
        
        if self._pose is None:
            return {"error": "Pose model not initialized", "pose_detected": False}
        
        start_time = time.time()
        
        try:
            import cv2
            
            # Convert BGR to RGB for MediaPipe
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Process image
            results = self._pose.process(rgb_image)
            
            self._last_inference_time_ms = (time.time() - start_time) * 1000
            
            if not results.pose_landmarks:
                return {
                    "pose_detected": False,
                    "message": "No pose detected",
                    "inference_time_ms": self._last_inference_time_ms
                }
            
            # Extract landmarks
            landmarks = self._extract_landmarks(results)
            
            if landmarks is None:
                return {
                    "pose_detected": False,
                    "message": "Failed to extract landmarks",
                    "inference_time_ms": self._last_inference_time_ms
                }
            
            # Calculate posture metrics
            head_forward_angle = self._calculate_head_forward_angle(landmarks)
            slouch_angle = self._calculate_slouch_angle(landmarks)
            shoulder_alignment = self._calculate_shoulder_alignment(landmarks)
            
            # Determine posture status
            head_forward_issue = abs(head_forward_angle) > self.HEAD_FORWARD_THRESHOLD_DEG
            slouch_issue = slouch_angle > self.SLOUCH_THRESHOLD_DEG
            
            # Calculate posture score (0-100, 100 = perfect)
            posture_score = 100.0
            posture_score -= min(30, abs(head_forward_angle) * 2)  # Max 30 points deduction
            posture_score -= min(30, slouch_angle * 1.5)           # Max 30 points deduction
            if not shoulder_alignment["is_level"]:
                posture_score -= 10
            posture_score = max(0, posture_score)
            
            # Compile issues list
            issues = []
            if head_forward_issue:
                issues.append({
                    "type": "head_forward",
                    "description": "Head positioned too far forward",
                    "angle": head_forward_angle,
                    "threshold": self.HEAD_FORWARD_THRESHOLD_DEG
                })
            
            if slouch_issue:
                issues.append({
                    "type": "slouching",
                    "description": "Thoracic spine angle indicates slouching",
                    "angle": slouch_angle,
                    "threshold": self.SLOUCH_THRESHOLD_DEG
                })
            
            if not shoulder_alignment["is_level"]:
                issues.append({
                    "type": "uneven_shoulders",
                    "description": f"{shoulder_alignment['higher_shoulder'].capitalize()} shoulder is higher",
                    "height_difference": shoulder_alignment["height_difference"]
                })
            
            result = {
                "pose_detected": True,
                "posture_score": round(posture_score, 1),
                "head_forward_angle": round(head_forward_angle, 2),
                "slouch_angle": round(slouch_angle, 2),
                "shoulder_alignment": shoulder_alignment,
                "issues": issues,
                "is_good_posture": len(issues) == 0,
                "inference_time_ms": self._last_inference_time_ms,
                "landmarks_count": 33
            }
            
            logger.debug(f"Posture analysis: score={posture_score:.1f} in {self._last_inference_time_ms:.1f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Posture analysis failed: {e}")
            return {"error": str(e), "pose_detected": False}
    
    def get_landmark_positions(self, image: np.ndarray) -> Optional[List[Dict[str, Any]]]:
        """
        Get all 33 landmark positions for visualization.
        
        Returns list of landmarks with normalized x, y, z coordinates.
        """
        if not self._initialized:
            self.initialize()
        
        if self._pose is None:
            return None
        
        try:
            import cv2
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self._pose.process(rgb_image)
            
            if not results.pose_landmarks:
                return None
            
            landmarks = []
            for idx, lm in enumerate(results.pose_landmarks.landmark):
                landmarks.append({
                    "index": idx,
                    "x": lm.x,
                    "y": lm.y,
                    "z": lm.z,
                    "visibility": lm.visibility
                })
            
            return landmarks
            
        except Exception as e:
            logger.error(f"Failed to get landmarks: {e}")
            return None
    
    def cleanup(self):
        """Release MediaPipe resources."""
        if self._pose:
            self._pose.close()
            self._pose = None
        self._initialized = False
        logger.info("Posture service cleaned up")
    
    @property
    def last_inference_time_ms(self) -> float:
        """Get the last inference time in milliseconds."""
        return self._last_inference_time_ms
    
    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
