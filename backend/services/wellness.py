import logging
import json
from typing import Optional

from services.jetson_client import ServicesClient
from services.wellness_scoring import WellnessScoringEngine
from models import AnalysisResult, AnalysisScores

logger = logging.getLogger(__name__)

class WellnessService:
    """
    Orchestrates the stateless wellness analysis flow:
    1. Triggers ML analysis via local services orchestrator
    2. Calculates scores
    3. Returns results directly
    """
    
    def __init__(self):
        self.services = ServicesClient()
        self.scoring = WellnessScoringEngine()

    async def perform_analysis(self, user_id: Optional[int] = None) -> AnalysisResult:
        """Run full analysis pipeline (Stateless)."""
        
        # 1. ML analysis
        ml_results = await self.services.run_full_analysis(user_id=user_id)
        
        # 2. Scoring
        overall_score, weights_used = self.scoring.calculate(
            skin_score=ml_results.skin_score,
            posture_score=ml_results.posture_score,
            eye_score=ml_results.eye_score,
        )
        
        # 3. Return Results (No DB Save)
        return AnalysisResult(
            id=0, # Stateless, no ID
            user_id=user_id or 0,
            timestamp="", # Could add current time if needed
            scores=AnalysisScores(
                skin=ml_results.skin_score,
                posture=ml_results.posture_score,
                eyes=ml_results.eye_score,
            ),
            overall_score=overall_score,
            weights_used=weights_used,
            captured_image=ml_results.captured_image
        )
