from fastapi import FastAPI
from pydantic import BaseModel
import logging
import random

app = FastAPI()
logger = logging.getLogger("service.posture")

class AnalysisRequest(BaseModel):
    image_path: str

@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    logger.info(f"Analyzing posture for: {request.image_path}")
    
    # TODO: Add Posture Analysis Logic here
    # 1. Load image from request.image_path
    # 2. Run MediaPipe Pose
    # 3. Calculate metrics
    
    # Dummy score
    score = random.randint(70, 100)
    
    return {
        "service": "posture",
        "score": score,
        "details": {
            "head_tilt": "15 deg",
            "shoulder_alignment": "OK"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
