from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class AnalysisRequest(BaseModel):
    user_id: int

class AnalysisScores(BaseModel):
    skin: Optional[float] = None
    posture: Optional[float] = None
    eyes: Optional[float] = None
    thermal: Optional[float] = None

class AnalysisResult(BaseModel):
    id: int
    user_id: int
    timestamp: str
    scores: AnalysisScores
    overall_score: float
    weights_used: Dict[str, float]
    captured_image: Optional[str] = None

class AnalysisHistory(BaseModel):
    id: int
    user_id: int
    timestamp: str
    skin_score: Optional[float]
    posture_score: Optional[float]
    eye_score: Optional[float]
    thermal_score: Optional[float]
    computed_score: float


# Voice models are defined in voice_orchestrator.py which is the active voice route.
# That module includes a richer VoiceAction (with a result field) and uses
# actions_run instead of actions to reflect executed-action semantics.
