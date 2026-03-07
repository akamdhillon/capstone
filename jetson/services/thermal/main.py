"""
Clarity+ Thermal Service (Ghost / Placeholder)
===============================================
Mock service that returns a randomised body temperature in the normal range
(36.0-37.0 C).

A real implementation would read from an MLX90640 or similar IR thermal
sensor mounted behind the mirror glass.  Because the thermal hardware is
not available in the current build, this ghost service keeps the orchestrator
pipeline intact by returning plausible placeholder data.

Runs on port 8006.
"""

from fastapi import FastAPI
from pydantic import BaseModel
import logging
import random

app = FastAPI(title="Clarity+ Thermal Service (Ghost)")
logger = logging.getLogger("service.thermal")

class AnalysisRequest(BaseModel):
    image_path: str

@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    logger.info(f"Analyzing thermal for: {request.image_path}")

    temp = 36.5 + random.uniform(-0.5, 0.5)

    return {
        "service": "thermal",
        "temperature": temp,
        "unit": "C"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
