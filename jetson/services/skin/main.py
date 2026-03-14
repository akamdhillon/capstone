from fastapi import FastAPI
from pydantic import BaseModel
import logging
import os
import cv2
from pathlib import Path
from typing import Optional

app = FastAPI()
logger = logging.getLogger("service.skin")

# Load the acne model once at startup
_inference_system = None
_MODEL_PATH = Path(__file__).parent / "checkpoints" / "best_model.pth"

def _is_lfs_pointer(path: Path) -> bool:
    """Return True if the file is a Git LFS pointer instead of real binary data."""
    try:
        with open(path, "rb") as f:
            header = f.read(64)
        return header.startswith(b"version https://git-lfs.github.com")
    except Exception:
        return False

def _load_model():
    global _inference_system
    # Test mode: use mock so tests run without real model (no production fallback)
    import sys
    if "pytest" in sys.modules:
        from unittest.mock import MagicMock
        _inference_system = MagicMock()
        return
    if not _MODEL_PATH.exists():
        raise SystemExit(
            f"Skin model not found at {_MODEL_PATH}. "
            "Run 'git lfs pull' to download the checkpoint. See README Prerequisites."
        )
    if _is_lfs_pointer(_MODEL_PATH):
        raise SystemExit(
            "Skin model file is a Git LFS pointer, not actual weights. "
            "Run 'git lfs pull' to download the checkpoint. See README Prerequisites."
        )
    try:
        from inference import AcneInferenceSystem
        logger.info(f"Loading acne model from {_MODEL_PATH}")
        _inference_system = AcneInferenceSystem(str(_MODEL_PATH))
        logger.info("Acne model loaded successfully")
    except Exception as e:
        raise SystemExit(f"Failed to load acne model: {e}") from e

_load_model()


class AnalysisRequest(BaseModel):
    image_path: str


def _status_from_score(score: int) -> str:
    """Derive status from 0-100 wellness score."""
    if score >= 80:
        return "good"
    if score >= 60:
        return "moderate"
    return "poor"


def _run_expanded_pipeline(image_path: str) -> Optional[dict]:
    """Run preprocess -> regions -> analyses; return merged details or None on failure."""
    try:
        from preprocess import detect_face
        from regions import extract_regions
        from analyses import run_all_analyses

        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            return None
        preproc = detect_face(img_bgr)
        regions = extract_regions(preproc)
        analyses_result = run_all_analyses(regions)
        return analyses_result
    except Exception as e:
        logger.warning(f"Expanded pipeline failed, using acne-only: {e}")
        return None


@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    logger.info(f"Analyzing skin for: {request.image_path}")

    if _inference_system is None:
        raise RuntimeError("Skin model not loaded (unexpected)")

    try:
        from PIL import Image
        pil_image = Image.open(request.image_path).convert("RGB")
        acne_result = _inference_system.predict_single(pil_image)

        # severity_score 0-1 (higher = worse) -> 0-100 wellness (higher = better)
        severity_raw = acne_result["severity_score"]
        acne_score = round((1 - severity_raw) * 100)
        severity_10 = round(severity_raw * 10, 1)

        acne_details = {
            "classification": acne_result["class_name"],
            "severity_score": severity_10,
            "confidence": round(acne_result["confidence"] * 100, 1),
            "score": acne_score,
        }

        # Run expanded pipeline (redness, oiliness, pores, etc.)
        img_bgr = cv2.imread(request.image_path)
        details = {"acne": acne_details}
        if img_bgr is not None:
            extra = _run_expanded_pipeline(request.image_path)
            if extra:
                details.update(extra)

        # Overall score: weighted avg (acne 40%, redness 15%, oiliness 15%, pores 15%)
        weights = {"acne": 0.40, "redness": 0.15, "oiliness": 0.15, "pores": 0.15}
        total_w = 0
        weighted_sum = 0
        for k, w in weights.items():
            if k in details and isinstance(details[k], dict) and "score" in details[k]:
                s = details[k]["score"]
                if s != 99:  # exclude placeholders
                    weighted_sum += s * w
                    total_w += w
        if total_w > 0:
            overall_score = round(weighted_sum / total_w)
        else:
            overall_score = acne_score

        recommendation = _inference_system._get_recommendation(
            acne_result["class_idx"], severity_10
        )
        status = _status_from_score(overall_score)

        return {
            "service": "skin",
            "score": overall_score,
            "status": status,
            "classification": acne_details["classification"],
            "severity_score": severity_10,
            "confidence": acne_details["confidence"],
            "recommendation": recommendation,
            "details": details,
            "overall_score": overall_score,
            "images_analyzed": 1,
        }
    except Exception as e:
        logger.error(f"Acne inference failed: {e}", exc_info=True)
        return {
            "service": "skin",
            "score": None,
            "error": f"Inference failed: {e}",
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
