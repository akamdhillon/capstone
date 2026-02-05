# =============================================================================
# CLARITY+ BACKEND - JETSON ML CLIENT
# =============================================================================
"""
Async HTTP client for communicating with Jetson ML inference services.
Handles parallel requests to multiple ML endpoints.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

# Request timeout in seconds
REQUEST_TIMEOUT = 10.0


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
    Async client for Jetson ML inference services.
    
    Communicates with:
    - Port 8001: Face Recognition
    - Port 8002: Skin Analysis  
    - Port 8003: Posture Detection
    - Port 8004: Eye Strain
    - Port 8005: Thermal (conditional)
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.jetson_base_url
    
    async def _make_request(
        self,
        port: int,
        endpoint: str,
        method: str = "POST",
        data: Optional[dict] = None
    ) -> tuple[Optional[dict], Optional[str]]:
        """
        Make a request to a Jetson service.
        
        Returns:
            Tuple of (response_data, error_message)
        """
        url = f"{self.base_url}:{port}{endpoint}"
        
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
    
    async def trigger_capture(self) -> tuple[bool, Optional[str]]:
        """
        Trigger image capture on Jetson cameras.
        
        Returns:
            Tuple of (success, error_message)
        """
        data, error = await self._make_request(
            port=self.settings.jetson_face_port,
            endpoint="/capture"
        )
        if error:
            return False, error
        return True, None
    
    async def get_face_recognition(self, user_id: Optional[int] = None) -> tuple[Optional[dict], Optional[str]]:
        """Get face recognition result."""
        return await self._make_request(
            port=self.settings.jetson_face_port,
            endpoint="/recognize",
            data={"user_id": user_id} if user_id else None
        )
    
    async def get_skin_analysis(self) -> tuple[Optional[dict], Optional[str]]:
        """Get skin analysis result from live camera feed."""
        return await self._make_request(
            port=self.settings.jetson_skin_port,
            endpoint="/analyze-live"
        )
    
    async def get_posture_analysis(self) -> tuple[Optional[dict], Optional[str]]:
        """Get posture analysis result from live camera feed."""
        return await self._make_request(
            port=self.settings.jetson_posture_port,
            endpoint="/analyze-live"
        )
    
    async def get_eye_analysis(self) -> tuple[Optional[dict], Optional[str]]:
        """Get eye strain analysis result from live camera feed."""
        return await self._make_request(
            port=self.settings.jetson_eye_port,
            endpoint="/analyze-live"
        )
    
    async def get_thermal_analysis(self) -> tuple[Optional[dict], Optional[str]]:
        """
        Get thermal analysis result.
        Returns None scores if thermal hardware is disabled.
        """
        if not self.settings.thermal_enabled:
            logger.debug("Thermal analysis skipped - hardware disabled")
            return {"score": None, "enabled": False}, None
        
        return await self._make_request(
            port=self.settings.jetson_thermal_port,
            endpoint="/read"
        )
    
    async def run_full_analysis(self, user_id: Optional[int] = None) -> MLResults:
        """
        Run full analysis pipeline in parallel.
        
        Triggers all ML services concurrently and aggregates results.
        
        Args:
            user_id: Optional user ID for face recognition
            
        Returns:
            MLResults container with all scores and details
        """
        results = MLResults()
        
        # Run all analyses in parallel
        tasks = [
            self.get_skin_analysis(),
            self.get_posture_analysis(),
            self.get_eye_analysis(),
            self.get_thermal_analysis()
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process skin results
        skin_resp, skin_err = responses[0] if not isinstance(responses[0], Exception) else (None, str(responses[0]))
        if skin_resp:
            results.skin_score = skin_resp.get("score")
            results.skin_details = skin_resp
        if skin_err:
            results.errors.append(f"Skin: {skin_err}")
        
        # Process posture results
        posture_resp, posture_err = responses[1] if not isinstance(responses[1], Exception) else (None, str(responses[1]))
        if posture_resp:
            results.posture_score = posture_resp.get("score")
            results.posture_details = posture_resp
        if posture_err:
            results.errors.append(f"Posture: {posture_err}")
        
        # Process eye results
        eye_resp, eye_err = responses[2] if not isinstance(responses[2], Exception) else (None, str(responses[2]))
        if eye_resp:
            results.eye_score = eye_resp.get("score")
            results.eye_details = eye_resp
        if eye_err:
            results.errors.append(f"Eye: {eye_err}")
        
        # Process thermal results
        thermal_resp, thermal_err = responses[3] if not isinstance(responses[3], Exception) else (None, str(responses[3]))
        if thermal_resp and thermal_resp.get("enabled", True):
            results.thermal_score = thermal_resp.get("score")
            results.thermal_details = thermal_resp
        if thermal_err:
            results.errors.append(f"Thermal: {thermal_err}")
        
        logger.info(
            f"Full analysis complete: skin={results.skin_score}, "
            f"posture={results.posture_score}, eyes={results.eye_score}, "
            f"thermal={results.thermal_score}, errors={len(results.errors)}"
        )
        
        return results
    
    async def health_check(self) -> dict[str, bool]:
        """
        Check health of all Jetson services.
        
        Returns:
            Dict mapping service name to health status
        """
        async def check_service(name: str, port: int) -> tuple[str, bool]:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(f"{self.base_url}:{port}/health")
                    return name, response.status_code == 200
            except Exception:
                return name, False
        
        services = [
            ("face_recognition", self.settings.jetson_face_port),
            ("skin_analysis", self.settings.jetson_skin_port),
            ("posture_detection", self.settings.jetson_posture_port),
            ("eye_strain", self.settings.jetson_eye_port),
        ]
        
        if self.settings.thermal_enabled:
            services.append(("thermal", self.settings.jetson_thermal_port))
        
        results = await asyncio.gather(*[check_service(n, p) for n, p in services])
        return dict(results)
