"""
Clarity+ Eye Strain Service (Placeholder)
==========================================
Mock service that returns randomised eye strain scores.

The real implementation would use the EAR (Eye Aspect Ratio) algorithm
combined with HSV sclera-redness analysis to compute blink rate, drowsiness,
and eye-strain metrics from camera frames.  Hardware for real-time eye
tracking is not yet integrated, so this service returns plausible placeholder
data (score 80-100) to keep the orchestrator pipeline functional.

Runs on port 8005.
"""

from fastapi import FastAPI
from pydantic import BaseModel
import logging
import random

app = FastAPI(title="Clarity+ Eye Strain Service (Placeholder)")
logger = logging.getLogger("service.eyes")

class AnalysisRequest(BaseModel):
    image_path: str

@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    logger.info(f"Analyzing eyes for: {request.image_path}")

    score = random.randint(80, 100)

    return {
        "service": "eyes",
        "score": score,
        "details": {
            "blink_rate": "12/min",
            "drowsiness": "Low"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
