# =============================================================================
# CLARITY+ BACKEND - JETSON ML CLIENT (UNIFIED)
# =============================================================================
"""
Async HTTP client for communicating with the Unified Jetson ML Service.
Single endpoint handles image capture and multi-model inference.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Dict

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

# Request timeout in seconds (Orchestrator needs more time to run all models)
REQUEST_TIMEOUT = 10.0
# Unified Port (should match Jetson main.py)
JETSON_PORT = 8001


@dataclass
class MLResults:
    """Container for all ML service results."""
    skin_score: Optional[float] = None
    posture_score: Optional[float] = None
    eye_score: Optional[float] = None
    thermal_score: Optional[float] = None
    skin_details: Optional[dict] = None
    posture_details: Optional[dict] = None
    eye_details: Optional[dict] = None
    thermal_details: Optional[dict] = None
    errors: list[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class JetsonClient:
    """
    Async client for the Unified Jetson ML Service.
    Communicates via Port 8001 (Unified Endpoint).
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = f"http://{self.settings.jetson_ip}:{JETSON_PORT}"
    
    async def _make_request(
        self,
        endpoint: str,
        method: str = "POST",
        data: Optional[dict] = None
    ) -> tuple[Optional[dict], Optional[str]]:
        """Make a request to the Jetson unified service."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                if method == "POST":
                    response = await client.post(url, json=data or {})
                else:
                    response = await client.get(url)
                
                response.raise_for_status()
                return response.json(), None
                
        except httpx.TimeoutException:
            error = f"Timeout connecting to {url}"
            logger.warning(error)
            return None, error
            
        except httpx.ConnectError:
            error = f"Cannot connect to Jetson service at {url}"
            logger.warning(error)
            return None, error
            
        except httpx.HTTPStatusError as e:
            error = f"HTTP error from {url}: {e.response.status_code}"
            logger.warning(error)
            return None, error
            
        except Exception as e:
            error = f"Unexpected error calling {url}: {str(e)}"
            logger.error(error)
            return None, error
    
    async def run_full_analysis(self, user_id: Optional[int] = None) -> MLResults:
        """
        Trigger full analysis via the unified One-Shot Endpoint.
        
        The Jetson Orchestrator handles image capture and all inference locally.
        """
        endpoint = "/analyze-all"
        payload = {
            "user_id": user_id,
            "include_image": True,
            "save_history": True
        }
        
        data, error = await self._make_request(endpoint, method="POST", data=payload)
        
        results = MLResults()
        
        if error:
            results.errors.append(f"Orchestrator failed: {error}")
            return results
        
        if not data.get("success", False):
            # Server reported partial or total failure
            server_errors = data.get("errors", [])
            results.errors.extend(server_errors)
            if not server_errors:
                 results.errors.append("Unknown orchestrator failure")
        
        # Parse Aggregated Scores
        scores = data.get("scores", {})
        results.skin_score = scores.get("skin")
        results.posture_score = scores.get("posture")
        results.eye_score = scores.get("eyes")
        results.thermal_score = scores.get("thermal")
        
        # Parse Details
        # The orchestrator returns 'face', 'skin', 'posture', ...
        results.skin_details = data.get("skin")
        results.posture_details = data.get("posture")
        results.eye_details = data.get("eyes")
        results.thermal_details = data.get("thermal")
        
        # Add image to details if present (hack for frontend compatibility)
        if data.get("image") and results.skin_details:
             results.skin_details["image"] = data.get("image")
        
        logger.info(
            f"Analysis complete: skin={results.skin_score}, "
            f"posture={results.posture_score}, eyes={results.eye_score}, "
            f"thermal={results.thermal_score}"
        )
        
        return results
    
    async def health_check(self) -> dict[str, bool]:
        """Check health of the unified service."""
        _, error = await self._make_request("/health", method="GET")
        is_healthy = error is None
        return {
            "unified_service": is_healthy,
            "orchestrator": is_healthy
        }
