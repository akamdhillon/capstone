"""
Clarity+ Skin Analysis Service
==============================
YOLOv8n inference for skin condition detection.
Optimized for TensorRT FP16 on NVIDIA Jetson.
Target: <200ms inference time.
"""

import logging
import time
from typing import Optional, Dict, Any, List
import numpy as np

from config import settings, get_model_path
from utils.tensorrt_loader import TensorRTEngine, load_engine, is_tensorrt_available

logger = logging.getLogger("clarity-ml.skin_analysis")

# YOLOv8 lazy import
_ultralytics = None


def _get_ultralytics():
    """Lazy load ultralytics for YOLO."""
    global _ultralytics
    if _ultralytics is None:
        try:
            from ultralytics import YOLO
            _ultralytics = YOLO
            logger.info("Ultralytics YOLO loaded successfully")
        except ImportError as e:
            logger.warning(f"Ultralytics not available: {e}")
    return _ultralytics


class SkinAnalysisService:
    """
    Skin Analysis service using YOLOv8n object detection.
    
    Target classes:
        - Acne (inflammatory)
        - Acne (non-inflammatory)
        - Wrinkles
        - Dark Spots
    
    Optimizations:
        - TensorRT FP16 engine when available
        - Fallback to PyTorch inference
    
    Performance target: <200ms per frame
    """
    
    # Detection class names
    CLASSES = [
        "acne_inflammatory",
        "acne_non_inflammatory", 
        "wrinkle",
        "dark_spot"
    ]
    
    # Confidence threshold for detections
    CONFIDENCE_THRESHOLD = 0.5
    
    # NMS threshold
    NMS_THRESHOLD = 0.45
    
    def __init__(self):
        self._model = None
        self._trt_engine: Optional[TensorRTEngine] = None
        self._initialized = False
        self._using_tensorrt = False
        
        # Performance tracking
        self._last_inference_time_ms: float = 0.0
    
    def initialize(self) -> bool:
        """
        Initialize the YOLOv8n model.
        Attempts TensorRT loading first, falls back to PyTorch.
        """
        # Try TensorRT first (FP16 optimized)
        if is_tensorrt_available():
            engine_path = get_model_path("yolov8n_skin.engine")
            self._trt_engine = load_engine("yolov8n_skin")
            
            if self._trt_engine is not None:
                self._using_tensorrt = True
                self._initialized = True
                logger.info("YOLOv8n loaded via TensorRT (FP16)")
                return True
        
        # Fallback to PyTorch/ONNX
        YOLO = _get_ultralytics()
        if YOLO is None:
            logger.error("Cannot initialize: YOLOv8 not available")
            return False
        
        try:
            # Check for custom trained model
            model_path = get_model_path("yolov8n_skin.pt")
            
            import os
            if os.path.exists(model_path):
                self._model = YOLO(model_path)
                logger.info(f"Loaded custom skin model: {model_path}")
            else:
                # Use pretrained YOLOv8n as placeholder
                self._model = YOLO("yolov8n.pt")
                logger.warning("Using pretrained YOLOv8n (no custom skin model found)")
            
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize YOLOv8: {e}")
            return False
    
    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for YOLOv8 inference."""
        import cv2
        
        # Resize to model input size
        input_size = (640, 640)
        resized = cv2.resize(image, input_size)
        
        # Convert BGR to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Normalize and transpose for NCHW format
        normalized = rgb.astype(np.float32) / 255.0
        transposed = np.transpose(normalized, (2, 0, 1))
        
        # Add batch dimension
        batched = np.expand_dims(transposed, axis=0)
        
        # Convert to FP16 if using TensorRT FP16
        if settings.MODEL_PRECISION == "FP16" and self._using_tensorrt:
            batched = batched.astype(np.float16)
        
        return batched
    
    def _postprocess(
        self,
        outputs: np.ndarray,
        original_shape: tuple,
        conf_threshold: float = None,
        nms_threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Post-process YOLOv8 outputs to detection results.
        
        Returns list of detections with boxes, confidence, and class.
        """
        if conf_threshold is None:
            conf_threshold = self.CONFIDENCE_THRESHOLD
        if nms_threshold is None:
            nms_threshold = self.NMS_THRESHOLD
        
        detections = []
        
        # Standard YOLOv8 output processing
        # Shape: (1, num_classes + 4, num_detections)
        try:
            # Transpose to (num_detections, num_classes + 4)
            outputs = outputs.squeeze(0).T
            
            for detection in outputs:
                # First 4 values are box coordinates
                x_center, y_center, width, height = detection[:4]
                
                # Remaining values are class scores
                class_scores = detection[4:]
                class_id = int(np.argmax(class_scores))
                confidence = float(class_scores[class_id])
                
                if confidence >= conf_threshold:
                    # Convert to original image coordinates
                    scale_x = original_shape[1] / 640
                    scale_y = original_shape[0] / 640
                    
                    x1 = int((x_center - width / 2) * scale_x)
                    y1 = int((y_center - height / 2) * scale_y)
                    x2 = int((x_center + width / 2) * scale_x)
                    y2 = int((y_center + height / 2) * scale_y)
                    
                    class_name = self.CLASSES[class_id] if class_id < len(self.CLASSES) else f"class_{class_id}"
                    
                    detections.append({
                        "class_id": class_id,
                        "class_name": class_name,
                        "confidence": confidence,
                        "bbox": {
                            "x1": max(0, x1),
                            "y1": max(0, y1),
                            "x2": min(original_shape[1], x2),
                            "y2": min(original_shape[0], y2)
                        }
                    })
        
        except Exception as e:
            logger.error(f"Post-processing failed: {e}")
        
        return detections
    
    def analyze(
        self,
        image: np.ndarray,
        confidence_threshold: float = None
    ) -> Dict[str, Any]:
        """
        Analyze skin conditions in an image.
        
        Args:
            image: BGR image as numpy array
            confidence_threshold: Optional custom confidence threshold
        
        Returns:
            Dict with detections and analysis summary
        """
        if not self._initialized:
            self.initialize()
        
        start_time = time.time()
        
        try:
            if self._using_tensorrt:
                # TensorRT inference path
                preprocessed = self._preprocess(image)
                raw_output = self._trt_engine.infer(preprocessed)
                
                if raw_output is None:
                    return {"error": "TensorRT inference failed", "detections": []}
                
                detections = self._postprocess(
                    raw_output,
                    image.shape,
                    conf_threshold=confidence_threshold
                )
                
            elif self._model is not None:
                # PyTorch inference path
                results = self._model(
                    image,
                    conf=confidence_threshold or self.CONFIDENCE_THRESHOLD,
                    verbose=False
                )
                
                detections = []
                for result in results:
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        class_name = self.CLASSES[class_id] if class_id < len(self.CLASSES) else result.names.get(class_id, f"class_{class_id}")
                        
                        detections.append({
                            "class_id": class_id,
                            "class_name": class_name,
                            "confidence": float(box.conf[0]),
                            "bbox": {
                                "x1": int(box.xyxy[0][0]),
                                "y1": int(box.xyxy[0][1]),
                                "x2": int(box.xyxy[0][2]),
                                "y2": int(box.xyxy[0][3])
                            }
                        })
            else:
                return {"error": "No model loaded", "detections": []}
            
            self._last_inference_time_ms = (time.time() - start_time) * 1000
            
            # Generate analysis summary
            summary = self._generate_summary(detections)
            
            result = {
                "detections": detections,
                "summary": summary,
                "count": len(detections),
                "inference_time_ms": self._last_inference_time_ms,
                "using_tensorrt": self._using_tensorrt
            }
            
            logger.debug(f"Skin analysis: {len(detections)} detections in {self._last_inference_time_ms:.1f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Skin analysis failed: {e}")
            return {"error": str(e), "detections": []}
    
    def _generate_summary(self, detections: List[Dict]) -> Dict[str, Any]:
        """Generate a summary of skin conditions detected."""
        summary = {
            "acne_inflammatory_count": 0,
            "acne_non_inflammatory_count": 0,
            "wrinkle_count": 0,
            "dark_spot_count": 0,
            "total_issues": len(detections),
            "severity_score": 0.0
        }
        
        for det in detections:
            class_name = det.get("class_name", "")
            if "inflammatory" in class_name and "non" not in class_name:
                summary["acne_inflammatory_count"] += 1
            elif "non_inflammatory" in class_name:
                summary["acne_non_inflammatory_count"] += 1
            elif "wrinkle" in class_name:
                summary["wrinkle_count"] += 1
            elif "dark_spot" in class_name:
                summary["dark_spot_count"] += 1
        
        # Calculate severity score (0-100)
        # Weighted by condition type
        severity = (
            summary["acne_inflammatory_count"] * 10 +
            summary["acne_non_inflammatory_count"] * 5 +
            summary["wrinkle_count"] * 3 +
            summary["dark_spot_count"] * 2
        )
        summary["severity_score"] = min(100.0, severity)
        
        return summary
    
    @property
    def last_inference_time_ms(self) -> float:
        """Get the last inference time in milliseconds."""
        return self._last_inference_time_ms
    
    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
