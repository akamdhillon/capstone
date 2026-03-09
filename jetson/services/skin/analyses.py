"""
Per-region OpenCV/NumPy skin analyses.
Returns 0-100 wellness scores (higher = better).
"""

import cv2
import numpy as np
from typing import Dict, Any, Optional

from regions import RegionCrop

# Placeholder for unimplemented analyses
PLACEHOLDER_SCORE = 99


def _masked_mean(channel: np.ndarray, mask: Optional[np.ndarray]) -> float:
    """Mean of channel where mask > 0."""
    if mask is not None and mask.size == channel.size:
        m = mask.astype(bool).flatten()
        vals = channel.flatten()[m]
        return float(np.mean(vals)) if len(vals) > 0 else 0.0
    return float(np.mean(channel))


def _masked_pixels(channel: np.ndarray, mask: Optional[np.ndarray]) -> np.ndarray:
    """Pixel values where mask > 0."""
    if mask is not None and mask.shape == channel.shape:
        return channel[mask > 0]
    return channel.flatten()


def redness(region: RegionCrop) -> Dict[str, Any]:
    """
    Redness from LAB a* channel (cheeks/nose).
    Higher a* = more red. Score = 100 - normalized(a*).
    """
    img = region.image
    if img.size == 0 or img.shape[0] < 3 or img.shape[1] < 3:
        return {"score": PLACEHOLDER_SCORE}
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    a_channel = lab[:, :, 1]  # a* typically 128 +/- range
    mean_a = _masked_mean(a_channel, region.mask)
    # a* ~100-140 for red skin; ~120-130 typical. Lower = less red.
    # Normalize: assume 125 = neutral, 140 = very red. score = 100 - (mean_a - 110) * 2
    raw_score = 100 - max(0, (mean_a - 110) * 2)
    score = int(np.clip(raw_score, 0, 100))
    return {"score": score}


def oiliness(region: RegionCrop) -> Dict[str, Any]:
    """
    Oiliness from HSV V channel highlight ratio (T-zone).
    High V = shiny. Score = 100 - normalized(highlight_ratio).
    """
    img = region.image
    if img.size == 0 or img.shape[0] < 3 or img.shape[1] < 3:
        return {"score": PLACEHOLDER_SCORE}
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:, :, 2]
    pixels = _masked_pixels(v_channel, region.mask)
    if len(pixels) < 10:
        return {"score": PLACEHOLDER_SCORE}
    highlight_ratio = np.sum(pixels > 240) / len(pixels)
    # highlight_ratio 0-0.3 typical. Higher = more oily
    raw_score = 100 - (highlight_ratio * 333)  # 0.3 -> ~0, 0 -> 100
    score = int(np.clip(raw_score, 0, 100))
    return {"score": score}


def skin_tone(region: RegionCrop) -> Dict[str, Any]:
    """
    Mean L, a, b on skin mask. Report values; score = 99 (informational).
    """
    img = region.image
    if img.size == 0 or img.shape[0] < 3 or img.shape[1] < 3:
        return {"L": 0, "a": 0, "b": 0, "score": PLACEHOLDER_SCORE}
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    L = round(float(_masked_mean(lab[:, :, 0], region.mask)), 1)
    a = round(float(_masked_mean(lab[:, :, 1], region.mask)), 1)
    b = round(float(_masked_mean(lab[:, :, 2], region.mask)), 1)
    return {"L": L, "a": a, "b": b, "score": PLACEHOLDER_SCORE}


def pores(region: RegionCrop) -> Dict[str, Any]:
    """
    Texture from Laplacian variance on L channel (nose+cheeks).
    High variance = rough/large pores. Score = 100 - normalized(var).
    """
    img = region.image
    if img.size == 0 or img.shape[0] < 3 or img.shape[1] < 3:
        return {"score": PLACEHOLDER_SCORE}
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    if region.mask is not None and region.mask.shape == gray.shape:
        var = np.var(lap[region.mask > 0])
    else:
        var = np.var(lap)
    # Variance 100-2000 typical. Lower = smoother
    raw_score = 100 - min(100, var / 15)  # scale so ~1500 -> 0
    score = int(np.clip(raw_score, 0, 100))
    return {"score": score}


def dark_spots(region: RegionCrop) -> Dict[str, Any]:
    """Placeholder: return 99."""
    return {"score": PLACEHOLDER_SCORE}


def wrinkles(region: RegionCrop) -> Dict[str, Any]:
    """Placeholder: return 99."""
    return {"score": PLACEHOLDER_SCORE}


def eye_bags(region: RegionCrop) -> Dict[str, Any]:
    """Placeholder: return 99."""
    return {"score": PLACEHOLDER_SCORE}


def run_all_analyses(regions: Dict[str, RegionCrop]) -> Dict[str, Dict[str, Any]]:
    """
    Run all analyses on available regions.
    Returns dict of analysis_name -> {score, ...}.
    """
    out: Dict[str, Dict[str, Any]] = {}

    # Redness: cheeks + nose
    for name in ["left_cheek", "right_cheek", "nose"]:
        if name in regions:
            r = redness(regions[name])
            if "redness" not in out:
                out["redness"] = r
            else:
                # Average if multiple regions
                prev = out["redness"]["score"]
                out["redness"]["score"] = int((prev + r["score"]) / 2)
            break
    if "redness" not in out and "full_face" in regions:
        out["redness"] = redness(regions["full_face"])

    # Oiliness: t_zone
    if "t_zone" in regions:
        out["oiliness"] = oiliness(regions["t_zone"])
    elif "full_face" in regions:
        out["oiliness"] = oiliness(regions["full_face"])

    # Skin tone: full face
    if "full_face" in regions:
        out["skin_tone"] = skin_tone(regions["full_face"])

    # Pores: nose + cheeks
    for name in ["nose", "left_cheek", "right_cheek"]:
        if name in regions:
            p = pores(regions[name])
            if "pores" not in out:
                out["pores"] = p
            else:
                prev = out["pores"]["score"]
                out["pores"]["score"] = int((prev + p["score"]) / 2)
            break
    if "pores" not in out and "full_face" in regions:
        out["pores"] = pores(regions["full_face"])

    # Placeholders
    r0 = regions.get("full_face") or next(iter(regions.values()), None)
    if r0:
        out["dark_spots"] = dark_spots(r0)
        out["wrinkles"] = wrinkles(r0)
        out["eye_bags"] = eye_bags(r0)

    return out
