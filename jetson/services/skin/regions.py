"""
Region extraction from face bbox for per-region skin analysis.
Proportional crops: forehead, cheeks, nose, t_zone.
"""

import cv2
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass

from preprocess import FacePreprocessResult


@dataclass
class RegionCrop:
    """A cropped region with optional mask."""
    image: np.ndarray  # BGR
    mask: Optional[np.ndarray] = None  # binary, same size as image


def extract_regions(result: FacePreprocessResult) -> Dict[str, RegionCrop]:
    """
    Extract facial regions from preprocess result.
    Uses proportional crops from face bbox.
    """
    crop = result.face_crop
    mask_full = result.skin_mask
    bbox = result.bbox
    if crop is None or bbox is None:
        return {}

    x, y, w, h = bbox
    # Mask aligned to face crop (same size as crop)
    mask = mask_full[y : y + h, x : x + w] if mask_full is not None else None
    regions: Dict[str, RegionCrop] = {}

    # Forehead: top 25% of face
    fh_h = int(h * 0.25)
    if fh_h > 5:
        fh_crop = crop[0:fh_h, :]
        fh_mask = mask[0:fh_h, :] if mask is not None else None
        regions["forehead"] = RegionCrop(image=fh_crop, mask=fh_mask)

    # Left cheek: left third, middle 50% vertically
    left_x = 0
    left_w = int(w / 3)
    mid_y = int(h * 0.25)
    mid_h = int(h * 0.5)
    if left_w > 5 and mid_h > 5:
        lc_crop = crop[mid_y : mid_y + mid_h, left_x : left_x + left_w]
        lc_mask = mask[mid_y : mid_y + mid_h, left_x : left_x + left_w] if mask is not None else None
        regions["left_cheek"] = RegionCrop(image=lc_crop, mask=lc_mask)

    # Right cheek: right third, middle 50% vertically
    right_x = int(w * 2 / 3)
    right_w = w - right_x
    if right_w > 5 and mid_h > 5:
        rc_crop = crop[mid_y : mid_y + mid_h, right_x : right_x + right_w]
        rc_mask = mask[mid_y : mid_y + mid_h, right_x : right_x + right_w] if mask is not None else None
        regions["right_cheek"] = RegionCrop(image=rc_crop, mask=rc_mask)

    # Nose: center 30% width, middle 50% height
    nose_x = int(w * 0.35)
    nose_w = int(w * 0.3)
    if nose_w > 5 and mid_h > 5:
        nose_crop = crop[mid_y : mid_y + mid_h, nose_x : nose_x + nose_w]
        nose_mask = mask[mid_y : mid_y + mid_h, nose_x : nose_x + nose_w] if mask is not None else None
        regions["nose"] = RegionCrop(image=nose_crop, mask=nose_mask)

    # T-zone: forehead + nose (top 50% vertically, center 40% width)
    tz_x = int(w * 0.3)
    tz_w = int(w * 0.4)
    tz_h = int(h * 0.5)
    if tz_w > 5 and tz_h > 5:
        tz_crop = crop[0 : tz_h, tz_x : tz_x + tz_w]
        tz_mask = mask[0 : tz_h, tz_x : tz_x + tz_w] if mask is not None else None
        regions["t_zone"] = RegionCrop(image=tz_crop, mask=tz_mask)

    # Full face for analyses that need it
    regions["full_face"] = RegionCrop(image=crop, mask=mask)

    return regions
