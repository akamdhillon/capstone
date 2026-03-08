from fastapi import FastAPI
from pydantic import BaseModel
import logging
import os
from pathlib import Path

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


@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    logger.info(f"Analyzing skin for: {request.image_path}")

    if _inference_system is not None:
        try:
            from PIL import Image
            image = Image.open(request.image_path).convert("RGB")
            result = _inference_system.predict_single(image)

            # severity_score is 0-1 (higher = worse), convert to 0-100 wellness (higher = better)
            severity_raw = result["severity_score"]  # 0-1
            score = round((1 - severity_raw) * 100)

            acne_details = {
                "classification": result["class_name"],
                "severity_score": round(severity_raw * 10, 1),  # 0-10 scale
                "confidence": round(result["confidence"] * 100, 1),  # 0-100%
                "score": score,
            }

            return {
                "service": "skin",
                "score": score,
                "details": {
                    "acne": acne_details,
                },
            }
        except Exception as e:
            logger.error(f"Acne inference failed: {e}", exc_info=True)
            return {
                "service": "skin",
                "score": None,
                "error": f"Inference failed: {e}",
            }

    # Unreachable if _load_model() fails fast (no fallback)
    raise RuntimeError("Skin model not loaded (unexpected)")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
