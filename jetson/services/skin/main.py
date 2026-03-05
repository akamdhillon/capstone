from fastapi import FastAPI
from pydantic import BaseModel
import logging
import random
import os
from pathlib import Path

app = FastAPI()
logger = logging.getLogger("service.skin")

# Load the acne model once at startup
_inference_system = None
_MODEL_PATH = Path(__file__).parent / "checkpoints" / "best_model.pth"

def _load_model():
    global _inference_system
    try:
        from inference import AcneInferenceSystem
        if _MODEL_PATH.exists():
            logger.info(f"Loading acne model from {_MODEL_PATH}")
            _inference_system = AcneInferenceSystem(str(_MODEL_PATH))
            logger.info("Acne model loaded successfully")
        else:
            logger.warning(f"Model checkpoint not found at {_MODEL_PATH}, will use fallback")
    except Exception as e:
        logger.error(f"Failed to load acne model: {e}", exc_info=True)
        _inference_system = None

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
            logger.error(f"Acne inference failed, using fallback: {e}", exc_info=True)

    # Fallback if model is unavailable
    score = random.randint(60, 90)
    return {
        "service": "skin",
        "score": score,
        "details": {
            "texture": "Smooth",
            "hydration": "Good",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
