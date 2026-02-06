from fastapi import FastAPI
from pydantic import BaseModel
import logging
import random

app = FastAPI()
logger = logging.getLogger("service.thermal")

class AnalysisRequest(BaseModel):
    image_path: str

@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    logger.info(f"Analyzing thermal for: {request.image_path}")
    
    # TODO: Add Thermal Camera Logic here
    # Thermal might not need image_path if it reads directly from sensor, 
    # but for consistency we keep the interface.
    
    temp = 36.5 + random.uniform(-0.5, 0.5)
    
    return {
        "service": "thermal",
        "temperature": temp,
        "unit": "C"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
