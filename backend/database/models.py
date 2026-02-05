# =============================================================================
# CLARITY+ BACKEND - DATABASE MODELS
# =============================================================================
"""
Pydantic models for database entities.
Used for request/response validation and type safety.
"""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


# =============================================================================
# USER MODELS
# =============================================================================

class UserBase(BaseModel):
    """Base user model."""
    name: str = Field(..., min_length=1, max_length=100)


class UserCreate(UserBase):
    """User creation request."""
    face_embedding: Optional[list[float]] = Field(
        default=None,
        description="Face embedding vector for recognition"
    )


class User(UserBase):
    """User response model."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserWithStats(User):
    """User with statistics."""
    current_streak: int = 0
    longest_streak: int = 0
    total_analyses: int = 0
    badges: list[str] = []


# =============================================================================
# FACE EMBEDDING MODELS
# =============================================================================

class FaceEmbedding(BaseModel):
    """Face embedding model (decrypted)."""
    id: int
    user_id: int
    embedding: list[float]
    created_at: datetime


class FaceEmbeddingCreate(BaseModel):
    """Face embedding creation request."""
    user_id: int
    embedding: list[float] = Field(
        ...,
        description="128-dimensional face embedding vector"
    )


# =============================================================================
# ANALYSIS MODELS
# =============================================================================

class AnalysisScores(BaseModel):
    """Individual category scores."""
    skin: Optional[float] = Field(default=None, ge=0, le=100)
    posture: Optional[float] = Field(default=None, ge=0, le=100)
    eyes: Optional[float] = Field(default=None, ge=0, le=100)
    thermal: Optional[float] = Field(default=None, ge=0, le=100)


class AnalysisResult(BaseModel):
    """Complete analysis result."""
    id: int
    user_id: int
    timestamp: datetime
    scores: AnalysisScores
    overall_score: float = Field(..., ge=0, le=100)
    weights_used: dict[str, float]


class AnalysisRequest(BaseModel):
    """Analysis trigger request."""
    user_id: int
    capture_image: bool = Field(
        default=True,
        description="Whether to capture new image or use latest cached"
    )


class AnalysisHistory(BaseModel):
    """Analysis history entry."""
    id: int
    user_id: int
    timestamp: datetime
    skin_score: Optional[float]
    posture_score: Optional[float]
    eye_score: Optional[float]
    thermal_score: Optional[float]
    computed_score: float


# =============================================================================
# DAILY METRICS MODELS
# =============================================================================

class DailyMetric(BaseModel):
    """Daily aggregated metrics."""
    id: int
    user_id: int
    date: date
    skin_score: Optional[float]
    posture_score: Optional[float]
    eye_score: Optional[float]
    thermal_score: Optional[float]
    overall_score: float


class DailyMetricCreate(BaseModel):
    """Create daily metric entry."""
    user_id: int
    date: date
    skin_score: Optional[float] = None
    posture_score: Optional[float] = None
    eye_score: Optional[float] = None
    thermal_score: Optional[float] = None
    overall_score: float


# =============================================================================
# GAMIFICATION MODELS
# =============================================================================

class Streak(BaseModel):
    """User streak information."""
    user_id: int
    current_streak: int = 0
    longest_streak: int = 0
    last_active_date: Optional[date] = None


class Badge(BaseModel):
    """Badge achievement."""
    id: int
    user_id: int
    badge_type: str
    awarded_at: datetime


class BadgeType:
    """Badge type constants."""
    POSTURE_PRO = "posture_pro"  # 7 consecutive days with posture >= 80
    CONSISTENT_GLOW = "consistent_glow"  # 30 days with skin >= 75
    FIRST_SCAN = "first_scan"  # First analysis completed
    WEEK_WARRIOR = "week_warrior"  # 7-day streak
    MONTH_MASTER = "month_master"  # 30-day streak


# =============================================================================
# JETSON SERVICE RESPONSE MODELS
# =============================================================================

class JetsonSkinResponse(BaseModel):
    """Skin analysis response from Jetson."""
    score: float = Field(..., ge=0, le=100)
    hydration: Optional[float] = None
    clarity: Optional[float] = None
    texture: Optional[float] = None


class JetsonPostureResponse(BaseModel):
    """Posture analysis response from Jetson."""
    score: float = Field(..., ge=0, le=100)
    head_tilt: Optional[float] = None
    shoulder_alignment: Optional[float] = None


class JetsonEyeResponse(BaseModel):
    """Eye strain analysis response from Jetson."""
    score: float = Field(..., ge=0, le=100)
    blink_rate: Optional[float] = None
    fatigue_level: Optional[float] = None


class JetsonThermalResponse(BaseModel):
    """Thermal analysis response from Jetson."""
    score: float = Field(..., ge=0, le=100)
    temperature: Optional[float] = None
    inflammation_detected: bool = False
