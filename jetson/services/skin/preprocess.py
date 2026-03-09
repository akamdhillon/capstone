"""
MediaPipe Face Mesh preprocessing for skin analysis pipeline.
Returns face bbox, 468 landmarks, and skin mask (convex hull of face oval).
"""

import cv2
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass

# MediaPipe Face Mesh FACE_OVAL landmark indices (outer contour)
FACE_OVAL_INDICES = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234
]


@dataclass
class FacePreprocessResult:
    """Result of face preprocessing."""
    success: bool
    bbox: Optional[Tuple[int, int, int, int]]  # x, y, w, h
    landmarks: Optional[np.ndarray]  # Nx3 (x, y, z) normalized or pixel coords
    skin_mask: Optional[np.ndarray]  # binary mask, same shape as image
    face_crop: Optional[np.ndarray]  # cropped face BGR


def detect_face(img_bgr: np.ndarray) -> FacePreprocessResult:
    """
    Run MediaPipe Face Mesh on a BGR image.
    Returns face bbox, landmarks, skin mask (convex hull), and face crop.
    """
    try:
        import mediapipe as mp
    except ImportError:
        return _fallback_full_image(img_bgr)

    h, w = img_bgr.shape[:2]
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    with mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    ) as face_mesh:
        results = face_mesh.process(rgb)

    if not results.multi_face_landmarks:
        return _fallback_full_image(img_bgr)

    lm = results.multi_face_landmarks[0]
    # Convert to pixel coordinates
    points = np.array([
        [int(lm.landmark[i].x * w), int(lm.landmark[i].y * h)]
        for i in range(len(lm.landmark))
    ], dtype=np.int32)

    # Bounding box with padding
    x_min = max(0, points[:, 0].min() - 20)
    x_max = min(w, points[:, 0].max() + 20)
    y_min = max(0, points[:, 1].min() - 20)
    y_max = min(h, points[:, 1].max() + 20)
    bbox = (x_min, y_min, x_max - x_min, y_max - y_min)

    # Skin mask: convex hull of FACE_OVAL
    oval_pts = points[FACE_OVAL_INDICES]
    hull = cv2.convexHull(oval_pts)
    skin_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillConvexPoly(skin_mask, hull, 255)

    # Face crop
    face_crop = img_bgr[y_min:y_max, x_min:x_max]

    return FacePreprocessResult(
        success=True,
        bbox=bbox,
        landmarks=points,
        skin_mask=skin_mask,
        face_crop=face_crop,
    )


def _fallback_full_image(img_bgr: np.ndarray) -> FacePreprocessResult:
    """No face detected: use full image as crop."""
    h, w = img_bgr.shape[:2]
    mask = np.ones((h, w), dtype=np.uint8) * 255
    return FacePreprocessResult(
        success=False,
        bbox=(0, 0, w, h),
        landmarks=None,
        skin_mask=mask,
        face_crop=img_bgr.copy(),
    )
