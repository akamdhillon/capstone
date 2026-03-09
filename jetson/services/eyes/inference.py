"""
Eye Strain Analyzer — MediaPipe Face Mesh + EAR, sclera redness, puffiness.

Reuses a single FaceMesh instance across requests.
"""

import numpy as np
import cv2

# MediaPipe Face Mesh landmark indices
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
LEFT_SCLERA = [33, 7, 163, 144, 145, 153, 154, 155, 133]
RIGHT_SCLERA = [362, 382, 381, 380, 374, 373, 390, 249, 263]
LEFT_LOWER_LID = [145, 153, 154, 155]
RIGHT_LOWER_LID = [374, 380, 381, 382]


def _compute_ear(landmarks, eye_indices: list[int], image_w: int, image_h: int) -> float:
    pts = [(landmarks[i].x * image_w, landmarks[i].y * image_h) for i in eye_indices]
    p1, p2, p3, p4, p5, p6 = [np.array(p, dtype=np.float64) for p in pts]
    ear = (np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / (2.0 * np.linalg.norm(p1 - p4) + 1e-8)
    return round(float(ear), 4)


def _compute_sclera_redness(
    frame_bgr: np.ndarray, landmarks, sclera_indices: list[int], image_w: int, image_h: int
) -> float:
    pts = np.array(
        [(int(landmarks[i].x * image_w), int(landmarks[i].y * image_h)) for i in sclera_indices],
        dtype=np.int32,
    )
    mask = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    sclera_pixels = hsv[mask == 255]
    if len(sclera_pixels) == 0:
        return 0.0
    red_mask = (
        ((sclera_pixels[:, 0] <= 10) | (sclera_pixels[:, 0] >= 160))
        & (sclera_pixels[:, 1] > 40)
    )
    redness_ratio = red_mask.sum() / len(sclera_pixels)
    return round(float(redness_ratio * 10), 2)


def _compute_puffiness_single(
    frame_bgr: np.ndarray,
    landmarks,
    lower_lid_indices: list[int],
    image_w: int,
    image_h: int,
    offset_px: int = 10,
) -> str:
    pts = [
        (int(landmarks[i].x * image_w), int(landmarks[i].y * image_h) + offset_px)
        for i in lower_lid_indices
    ]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0 = max(0, min(xs) - 5)
    x1 = min(frame_bgr.shape[1], max(xs) + 5)
    y0 = max(0, min(ys) - 5)
    y1 = min(frame_bgr.shape[0], max(ys) + 10)
    if x1 <= x0 or y1 <= y0:
        return "Unknown"
    region = frame_bgr[y0:y1, x0:x1]
    if region.size == 0:
        return "Unknown"
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(np.mean(gray))
    if mean_brightness < 80:
        return "High"
    if mean_brightness < 120:
        return "Moderate"
    return "Low"


def _classify_eye_openness(ear: float) -> str:
    if ear > 0.30:
        return "Open"
    if ear >= 0.20:
        return "Partial"
    return "Closed"


def _classify_drowsiness(ear: float, blink_rate: float | None) -> str:
    if ear < 0.20:
        return "High"
    if ear < 0.25:
        if blink_rate is not None and blink_rate < 8:
            return "Moderate"
        return "Mild"
    if blink_rate is not None and blink_rate < 8:
        return "Mild"
    return "None"


def compute_eye_score(
    ear: float, redness: float, puffiness: str, blink_rate: float | None
) -> int:
    ear_clamped = max(0.0, min(ear, 0.40))
    ear_score = (ear_clamped / 0.40) * 40
    redness_score = max(0, 30 - (redness * 3))
    puffiness_score = {"Low": 15, "Moderate": 8, "High": 0, "Unknown": 10}.get(
        puffiness, 10
    )
    if blink_rate is not None:
        if 8 <= blink_rate <= 21:
            blink_score = 15
        elif (5 <= blink_rate < 8) or (21 < blink_rate <= 25):
            blink_score = 8
        else:
            blink_score = 0
        total = ear_score + redness_score + puffiness_score + blink_score
    else:
        total = (ear_score + redness_score + puffiness_score) / 85 * 100
    return round(min(100, max(0, total)))


def _blink_rate_status(blink_rate: float | None) -> str | None:
    if blink_rate is None:
        return None
    if blink_rate < 8:
        return "Low — possible screen fatigue"
    if 8 <= blink_rate <= 21:
        return "Normal"
    return "Elevated — possible irritation"


class EyeStrainAnalyzer:
    """MediaPipe Face Mesh + EAR, sclera redness, puffiness, score."""

    def __init__(self, static_image_mode: bool = False):
        import mediapipe as mp

        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=static_image_mode,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def analyze_frame(
        self, frame_bgr: np.ndarray, blink_rate: float | None = None
    ) -> dict | None:
        """
        Process a single BGR frame. Returns metrics dict or None if no face.
        """
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self._face_mesh.process(rgb)
        if not results.multi_face_landmarks:
            return None
        lm = results.multi_face_landmarks[0]
        landmarks = lm.landmark  # MediaPipe 0.10+ uses .landmark for indexing

        ear_left = _compute_ear(landmarks, LEFT_EYE, w, h)
        ear_right = _compute_ear(landmarks, RIGHT_EYE, w, h)
        ear = round((ear_left + ear_right) / 2.0, 4)

        red_left = _compute_sclera_redness(frame_bgr, landmarks, LEFT_SCLERA, w, h)
        red_right = _compute_sclera_redness(frame_bgr, landmarks, RIGHT_SCLERA, w, h)
        redness = round((red_left + red_right) / 2.0, 2)

        puff_left = _compute_puffiness_single(frame_bgr, landmarks, LEFT_LOWER_LID, w, h)
        puff_right = _compute_puffiness_single(frame_bgr, landmarks, RIGHT_LOWER_LID, w, h)
        # Prefer the worse (darker) puffiness
        puff_order = {"High": 0, "Moderate": 1, "Low": 2, "Unknown": 1}
        puffiness = puff_left if puff_order.get(puff_left, 1) <= puff_order.get(puff_right, 1) else puff_right

        eye_openness = _classify_eye_openness(ear)
        drowsiness = _classify_drowsiness(ear, blink_rate)
        score = compute_eye_score(ear, redness, puffiness, blink_rate)

        return {
            "ear": ear,
            "eye_openness": eye_openness,
            "sclera_redness": redness,
            "puffiness": puffiness,
            "blink_rate": blink_rate,
            "drowsiness": drowsiness,
            "score": score,
        }
