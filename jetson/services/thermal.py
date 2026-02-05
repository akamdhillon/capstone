"""
Clarity+ Thermal Service (Ghost Service)
========================================
Placeholder thermal sensor service that returns null when disabled.
Implements the FeatureToggle pattern for graceful degradation.

Status: DISABLED by default (ENABLE_THERMAL=false)
"""

import logging
from typing import Optional, Dict, Any

from config import settings

logger = logging.getLogger("clarity-ml.thermal")


class ThermalService:
    """
    Thermal sensor service - Ghost Service implementation.
    
    When ENABLE_THERMAL=False (default):
        - Returns null/0.0 values for all metrics
        - Does not break orchestrator wellness score logic
        - Logs that thermal is disabled
    
    When ENABLE_THERMAL=True:
        - Would connect to physical thermal sensor
        - Return actual temperature readings
        - Currently placeholder implementation
    
    Ghost Service Pattern:
        This service always responds with valid structure but
        null data when disabled, allowing the orchestrator to
        handle the absence gracefully without special-casing.
    """
    
    def __init__(self):
        self._enabled = settings.ENABLE_THERMAL
        self._initialized = False
        
        # Placeholder for future thermal sensor connection
        self._sensor = None
        
        logger.info(f"Thermal service initialized (enabled={self._enabled})")
    
    def initialize(self) -> bool:
        """
        Initialize thermal sensor connection.
        
        Returns True if:
            - Service is disabled (ghost mode)
            - Service is enabled AND sensor connection succeeds
        """
        if not self._enabled:
            # Ghost service mode - always "successful"
            self._initialized = True
            logger.info("Thermal service in ghost mode (disabled)")
            return True
        
        # When enabled, attempt to connect to thermal sensor
        # This is a placeholder for actual hardware integration
        try:
            # TODO: Implement actual thermal sensor connection
            # Example sensors: MLX90640, FLIR Lepton, AMG8833
            #
            # self._sensor = ThermalCamera()
            # self._sensor.connect()
            
            self._initialized = True
            logger.info("Thermal sensor connected (placeholder)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize thermal sensor: {e}")
            return False
    
    def read(self) -> Dict[str, Any]:
        """
        Read thermal data from sensor.
        
        Returns:
            Dict with temperature data or null values if disabled.
            Structure is consistent regardless of enabled state.
        """
        # Ghost Service Response when disabled
        if not self._enabled:
            return {
                "enabled": False,
                "temperature": None,
                "unit": "celsius",
                "face_temperature": None,
                "ambient_temperature": None,
                "thermal_map": None,
                "message": "Thermal service is disabled"
            }
        
        # Enabled but not initialized
        if not self._initialized:
            self.initialize()
        
        # Placeholder response for enabled state
        # TODO: Replace with actual sensor readings
        try:
            # Simulated thermal data structure
            # In production, this would read from hardware
            return {
                "enabled": True,
                "temperature": 0.0,           # TODO: Read from sensor
                "unit": "celsius",
                "face_temperature": 0.0,      # TODO: Face ROI temperature
                "ambient_temperature": 0.0,   # TODO: Ambient reading
                "thermal_map": None,          # TODO: 2D thermal array
                "sensor_status": "placeholder",
                "message": "Thermal sensor not yet implemented"
            }
            
        except Exception as e:
            logger.error(f"Thermal read failed: {e}")
            return {
                "enabled": True,
                "temperature": None,
                "error": str(e)
            }
    
    def get_face_temperature(self) -> Optional[float]:
        """
        Get face temperature reading.
        
        Returns:
            Temperature in Celsius, or None if disabled/unavailable.
        """
        if not self._enabled:
            return None
        
        # Placeholder
        return None
    
    def get_thermal_map(self) -> Optional[list]:
        """
        Get 2D thermal map array.
        
        Returns:
            2D array of temperatures, or None if disabled/unavailable.
        """
        if not self._enabled:
            return None
        
        # Placeholder
        return None
    
    def cleanup(self):
        """Release thermal sensor resources."""
        if self._sensor is not None:
            # TODO: Disconnect sensor
            self._sensor = None
        
        self._initialized = False
        logger.info("Thermal service cleaned up")
    
    @property
    def is_enabled(self) -> bool:
        """Check if thermal service is enabled."""
        return self._enabled
    
    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
    
    @staticmethod
    def get_null_response() -> Dict[str, Any]:
        """
        Get standard null response for disabled state.
        
        Use this in orchestrator when thermal is disabled to ensure
        consistent response structure.
        """
        return {
            "enabled": False,
            "temperature": None,
            "unit": "celsius",
            "face_temperature": None,
            "ambient_temperature": None,
            "thermal_map": None,
            "message": "Thermal service is disabled"
        }
