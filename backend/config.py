# =============================================================================
# CLARITY+ BACKEND - CONFIGURATION
# =============================================================================
"""
Configuration management using Pydantic Settings.
Handles environment variables, weight redistribution, and encryption key.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Network Configuration
    jetson_ip: str = Field(default="192.168.10.2", alias="JETSON_IP")
    rpi_ip: str = Field(default="192.168.10.1", alias="RPI_IP")
    
    # Database
    database_url: str = Field(
        default="sqlite:///data/clarity.db",
        alias="DATABASE_URL"
    )
    
    # Feature Toggles
    thermal_enabled: bool = Field(default=False, alias="THERMAL_ENABLED")
    dev_mode: bool = Field(default=False, alias="DEV_MODE")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # Security - AES-256 requires 32 bytes (256 bits)
    encryption_key: str = Field(
        default="clarity_default_key_change_in_prod!",  # 32 chars
        alias="ENCRYPTION_KEY"
    )
    
    # Janitor Configuration
    image_retention_days: int = Field(default=30, alias="IMAGE_RETENTION_DAYS")
    janitor_schedule_hour: int = Field(default=2, alias="JANITOR_SCHEDULE_HOUR")
    
    # Jetson Service Ports
    jetson_face_port: int = 8001
    jetson_skin_port: int = 8002
    jetson_posture_port: int = 8003
    jetson_eye_port: int = 8004
    jetson_thermal_port: int = 8005
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def jetson_base_url(self) -> str:
        """Base URL for Jetson ML services."""
        return f"http://{self.jetson_ip}"
    
    @property
    def weights(self) -> dict[str, float]:
        """
        Get wellness scoring weights based on thermal hardware status.
        
        Default weights (thermal enabled):
            Skin: 30%, Posture: 25%, Eyes: 25%, Thermal: 20%
        
        Redistributed weights (thermal disabled):
            Skin: 40%, Posture: 35%, Eyes: 25%, Thermal: 0%
        """
        if self.thermal_enabled:
            return {
                "skin": 0.30,
                "posture": 0.25,
                "eyes": 0.25,
                "thermal": 0.20
            }
        else:
            # Redistribute thermal's 20% to skin (+10%) and posture (+10%)
            return {
                "skin": 0.40,
                "posture": 0.35,
                "eyes": 0.25,
                "thermal": 0.00
            }


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance for dependency injection."""
    return Settings()
