"""
Clarity+ Face Recognition Service
=================================
DeepFace integration with RetinaFace detection and FaceNet512 embeddings.
Optimized for TensorRT FP16 inference on NVIDIA Jetson.
Target: <100ms inference time.
"""

import logging
import time
from typing import Optional, Dict, Any, List, Tuple
import numpy as np

from config import settings

logger = logging.getLogger("clarity-ml.face_recognition")

# DeepFace lazy import for optional dependency
_deepface = None


def _get_deepface():
    """Lazy load DeepFace to handle import errors gracefully."""
    global _deepface
    if _deepface is None:
        try:
            from deepface import DeepFace
            _deepface = DeepFace
            logger.info("DeepFace loaded successfully")
        except ImportError as e:
            logger.warning(f"DeepFace not available: {e}")
    return _deepface


class FaceRecognitionService:
    """
    Face Recognition service using DeepFace.
    
    Pipeline:
        1. Detect faces using RetinaFace
        2. Align facial landmarks
        3. Generate 512-dimensional FaceNet embedding
        4. Return embedding for orchestrator DB matching
    
    Performance target: <100ms per frame
    """
    
    # Supported detector backends
    DETECTOR_BACKEND = "retinaface"  # Best accuracy on Jetson
    EMBEDDING_MODEL = "Facenet512"   # 512-dim embeddings
    
    def __init__(self):
        self._initialized = False
        self._deepface = None
        
        # Performance tracking
        self._last_inference_time_ms: float = 0.0
    
    def initialize(self) -> bool:
        """
        Initialize the face recognition models.
        Pre-loads models for faster first inference.
        """
        self._deepface = _get_deepface()
        
        if self._deepface is None:
            logger.error("Cannot initialize: DeepFace not available")
            return False
        
        try:
            # Pre-load models by running dummy inference
            logger.info("Pre-loading face recognition models...")
            dummy_image = np.zeros((224, 224, 3), dtype=np.uint8)
            
            # This will trigger model download/load
            try:
                self._deepface.represent(
                    img_path=dummy_image,
                    model_name=self.EMBEDDING_MODEL,
                    detector_backend=self.DETECTOR_BACKEND,
                    enforce_detection=False
                )
            except Exception:
                pass  # Expected to fail on dummy image, but models are loaded
            
            self._initialized = True
            logger.info("Face recognition models loaded")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize face recognition: {e}")
            return False
    
    def detect_faces(
        self,
        image: np.ndarray,
        enforce_detection: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Detect faces in an image.
        
        Args:
            image: BGR image as numpy array
            enforce_detection: If True, raise error when no face found
        
        Returns:
            List of detected faces with bounding boxes and confidence
        """
        if not self._initialized:
            self.initialize()
        
        if self._deepface is None:
            return []
        
        start_time = time.time()
        
        try:
            # DeepFace detection
            faces = self._deepface.extract_faces(
                img_path=image,
                detector_backend=self.DETECTOR_BACKEND,
                enforce_detection=enforce_detection,
                align=True
            )
            
            self._last_inference_time_ms = (time.time() - start_time) * 1000
            
            results = []
            for face in faces:
                results.append({
                    "confidence": face.get("confidence", 0.0),
                    "facial_area": face.get("facial_area", {}),
                    "aligned_face": face.get("face", None)
                })
            
            logger.debug(f"Detected {len(results)} faces in {self._last_inference_time_ms:.1f}ms")
            return results
            
        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            return []
    
    def generate_embedding(
        self,
        image: np.ndarray,
        enforce_detection: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Generate 512-dimensional face embedding for an image.
        
        Args:
            image: BGR image as numpy array (should contain one face)
            enforce_detection: If True, raise error when no face found
        
        Returns:
            Dict with embedding vector and metadata, or None if failed
        """
        if not self._initialized:
            self.initialize()
        
        if self._deepface is None:
            return None
        
        start_time = time.time()
        
        try:
            # Generate embedding using FaceNet512
            embeddings = self._deepface.represent(
                img_path=image,
                model_name=self.EMBEDDING_MODEL,
                detector_backend=self.DETECTOR_BACKEND,
                enforce_detection=enforce_detection
            )
            
            self._last_inference_time_ms = (time.time() - start_time) * 1000
            
            if not embeddings:
                return None
            
            # Take first detected face
            embedding_data = embeddings[0]
            
            result = {
                "embedding": embedding_data.get("embedding", []),
                "embedding_dim": len(embedding_data.get("embedding", [])),
                "facial_area": embedding_data.get("facial_area", {}),
                "model": self.EMBEDDING_MODEL,
                "inference_time_ms": self._last_inference_time_ms
            }
            
            logger.debug(f"Generated {result['embedding_dim']}-dim embedding in {self._last_inference_time_ms:.1f}ms")
            
            # Performance warning if exceeding target
            if self._last_inference_time_ms > settings.INFERENCE_TIMEOUT_MS:
                logger.warning(f"Embedding generation exceeded target: {self._last_inference_time_ms:.1f}ms > {settings.INFERENCE_TIMEOUT_MS}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None
    
    def compare_embeddings(
        self,
        embedding1: List[float],
        embedding2: List[float],
        threshold: float = 0.4
    ) -> Dict[str, Any]:
        """
        Compare two face embeddings for similarity.
        
        Args:
            embedding1: First 512-dim embedding
            embedding2: Second 512-dim embedding
            threshold: Distance threshold (lower = stricter match)
        
        Returns:
            Dict with match result and distance metric
        """
        try:
            # Euclidean distance
            e1 = np.array(embedding1)
            e2 = np.array(embedding2)
            distance = float(np.linalg.norm(e1 - e2))
            
            # Cosine similarity
            cosine_sim = float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2)))
            
            is_match = distance < threshold
            
            return {
                "is_match": is_match,
                "distance": distance,
                "cosine_similarity": cosine_sim,
                "threshold": threshold
            }
            
        except Exception as e:
            logger.error(f"Embedding comparison failed: {e}")
            return {
                "is_match": False,
                "error": str(e)
            }
    
    @property
    def last_inference_time_ms(self) -> float:
        """Get the last inference time in milliseconds."""
        return self._last_inference_time_ms
    
    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
