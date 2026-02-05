# =============================================================================
# CLARITY+ BACKEND - DATABASE PACKAGE
# =============================================================================
"""Database module exports."""

from .connection import get_db, init_database, close_database
from .models import User, FaceEmbedding, DailyMetric, AnalysisHistory, Streak, Badge

__all__ = [
    "get_db",
    "init_database", 
    "close_database",
    "User",
    "FaceEmbedding",
    "DailyMetric",
    "AnalysisHistory",
    "Streak",
    "Badge"
]
