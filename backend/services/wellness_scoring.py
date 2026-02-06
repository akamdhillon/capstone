# =============================================================================
# CLARITY+ BACKEND - WELLNESS SCORING ENGINE
# =============================================================================
"""
Wellness Scoring Engine that aggregates ML analysis results into a 0-100 score.
Implements weighted formula with dynamic thermal weight redistribution.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class AnalysisScores:
    """Container for individual analysis scores."""
    skin: Optional[float] = None
    posture: Optional[float] = None
    eyes: Optional[float] = None
    thermal: Optional[float] = None


class WellnessScoringEngine:
    """
    Wellness Scoring Engine.
    
    Aggregates scores from individual ML services using weighted formula:
    - Default: Skin (30%) + Posture (25%) + Eyes (25%) + Thermal (20%)
    - Without thermal: Skin (40%) + Posture (35%) + Eyes (25%)
    """
    
    def __init__(self):
        self.settings = settings
        self._weights = self.settings.weights
    
    @property
    def weights(self) -> dict[str, float]:
        """Current scoring weights based on thermal hardware status."""
        return self._weights
    
    @property
    def thermal_enabled(self) -> bool:
        """Whether thermal hardware is connected."""
        return self.settings.THERMAL_ENABLED
    
    def calculate(
        self,
        skin_score: Optional[float] = None,
        posture_score: Optional[float] = None,
        eye_score: Optional[float] = None,
        thermal_score: Optional[float] = None
    ) -> tuple[float, dict[str, float]]:
        """
        Calculate the overall wellness score.
        
        Args:
            skin_score: Skin analysis score (0-100)
            posture_score: Posture analysis score (0-100)
            eye_score: Eye strain score (0-100)
            thermal_score: Thermal analysis score (0-100)
            
        Returns:
            Tuple of (overall_score, weights_used)
        """
        scores = {
            "skin": skin_score,
            "posture": posture_score,
            "eyes": eye_score,
            "thermal": thermal_score
        }
        
        # Filter out None values and get available weights
        available = {k: v for k, v in scores.items() if v is not None}
        
        if not available:
            logger.warning("No valid scores provided for wellness calculation")
            return 0.0, self._weights
        
        # Calculate weighted sum using available scores
        total_weight = 0.0
        weighted_sum = 0.0
        
        for category, score in available.items():
            weight = self._weights.get(category, 0.0)
            if weight > 0:
                weighted_sum += score * weight
                total_weight += weight
        
        # Normalize if not all categories available
        if total_weight > 0:
            # If some categories are missing, normalize the weights
            if total_weight < 1.0:
                overall = weighted_sum / total_weight
            else:
                overall = weighted_sum
        else:
            overall = 0.0
        
        # Clamp to 0-100 range
        overall = max(0.0, min(100.0, overall))
        
        logger.debug(
            f"Wellness score calculated: {overall:.1f} "
            f"(skin={skin_score}, posture={posture_score}, "
            f"eyes={eye_score}, thermal={thermal_score})"
        )
        
        return round(overall, 2), self._weights


def calculate_wellness_score(
    skin_score: Optional[float] = None,
    posture_score: Optional[float] = None,
    eye_score: Optional[float] = None,
    thermal_score: Optional[float] = None
) -> tuple[float, dict[str, float]]:
    """
    Convenience function for wellness score calculation.
    
    Args:
        skin_score: Skin analysis score (0-100)
        posture_score: Posture analysis score (0-100)
        eye_score: Eye strain score (0-100)
        thermal_score: Thermal analysis score (0-100)
        
    Returns:
        Tuple of (overall_score, weights_used)
    """
    engine = WellnessScoringEngine()
    return engine.calculate(
        skin_score=skin_score,
        posture_score=posture_score,
        eye_score=eye_score,
        thermal_score=thermal_score
    )
