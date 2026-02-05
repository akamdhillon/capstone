# =============================================================================
# CLARITY+ BACKEND - ANALYSIS ROUTES
# =============================================================================
"""
API routes for wellness analysis operations.
Handles triggering ML pipeline and retrieving analysis history.
"""

import json
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

import aiosqlite

from config import get_settings
from database.connection import get_db
from database.models import AnalysisRequest, AnalysisResult, AnalysisScores, AnalysisHistory
from services.wellness_scoring import WellnessScoringEngine
from services.jetson_client import JetsonClient
from services.gamification import GamificationService

logger = logging.getLogger(__name__)
router = APIRouter()

settings = get_settings()


@router.post("/analyze", response_model=AnalysisResult)
async def trigger_analysis(
    request: AnalysisRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Trigger a full wellness analysis.
    
    1. Sends parallel requests to Jetson ML services
    2. Calculates weighted wellness score
    3. Stores results in database
    4. Updates gamification (streaks, badges)
    """
    user_id = request.user_id
    
    # Verify user exists
    cursor = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="User not found")
    
    # Trigger ML analysis on Jetson
    client = JetsonClient()
    ml_results = await client.run_full_analysis(user_id=user_id)
    
    # Calculate wellness score
    engine = WellnessScoringEngine()
    overall_score, weights_used = engine.calculate(
        skin_score=ml_results.skin_score,
        posture_score=ml_results.posture_score,
        eye_score=ml_results.eye_score,
        thermal_score=ml_results.thermal_score
    )
    
    # Store raw results as JSON
    raw_results = {
        "skin": ml_results.skin_details,
        "posture": ml_results.posture_details,
        "eyes": ml_results.eye_details,
        "thermal": ml_results.thermal_details,
        "errors": ml_results.errors
    }
    
    # Insert analysis history
    cursor = await db.execute(
        """INSERT INTO analysis_history 
           (user_id, raw_results, skin_score, posture_score, eye_score, thermal_score, computed_score)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            json.dumps(raw_results),
            ml_results.skin_score,
            ml_results.posture_score,
            ml_results.eye_score,
            ml_results.thermal_score,
            overall_score
        )
    )
    analysis_id = cursor.lastrowid
    
    # Update or insert daily metrics
    today = date.today().isoformat()
    await db.execute(
        """INSERT INTO daily_metrics (user_id, date, skin_score, posture_score, eye_score, thermal_score, overall_score)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id, date) DO UPDATE SET
           skin_score = excluded.skin_score,
           posture_score = excluded.posture_score,
           eye_score = excluded.eye_score,
           thermal_score = excluded.thermal_score,
           overall_score = excluded.overall_score""",
        (
            user_id,
            today,
            ml_results.skin_score,
            ml_results.posture_score,
            ml_results.eye_score,
            ml_results.thermal_score,
            overall_score
        )
    )
    
    await db.commit()
    
    # Update gamification
    gamification = GamificationService(db)
    await gamification.update_streak(user_id)
    await gamification.check_performance_badges(
        user_id,
        skin_score=ml_results.skin_score,
        posture_score=ml_results.posture_score
    )
    
    # Get timestamp for response
    cursor = await db.execute(
        "SELECT timestamp FROM analysis_history WHERE id = ?",
        (analysis_id,)
    )
    row = await cursor.fetchone()
    
    logger.info(f"Analysis completed for user {user_id}: score={overall_score}")
    
    return AnalysisResult(
        id=analysis_id,
        user_id=user_id,
        timestamp=row[0],
        scores=AnalysisScores(
            skin=ml_results.skin_score,
            posture=ml_results.posture_score,
            eyes=ml_results.eye_score,
            thermal=ml_results.thermal_score
        ),
        overall_score=overall_score,
        weights_used=weights_used
    )


@router.get("/analysis/{analysis_id}", response_model=AnalysisHistory)
async def get_analysis(
    analysis_id: int,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Retrieve a specific analysis by ID."""
    cursor = await db.execute(
        """SELECT id, user_id, timestamp, skin_score, posture_score, 
                  eye_score, thermal_score, computed_score
           FROM analysis_history WHERE id = ?""",
        (analysis_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return AnalysisHistory(
        id=row[0],
        user_id=row[1],
        timestamp=row[2],
        skin_score=row[3],
        posture_score=row[4],
        eye_score=row[5],
        thermal_score=row[6],
        computed_score=row[7]
    )


@router.get("/analysis/history/{user_id}")
async def get_analysis_history(
    user_id: int,
    limit: int = Query(default=10, le=100),
    offset: int = Query(default=0, ge=0),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Get paginated analysis history for a user.
    """
    # Verify user exists
    cursor = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get total count
    cursor = await db.execute(
        "SELECT COUNT(*) FROM analysis_history WHERE user_id = ?",
        (user_id,)
    )
    total = (await cursor.fetchone())[0]
    
    # Get paginated results
    cursor = await db.execute(
        """SELECT id, user_id, timestamp, skin_score, posture_score,
                  eye_score, thermal_score, computed_score
           FROM analysis_history 
           WHERE user_id = ?
           ORDER BY timestamp DESC
           LIMIT ? OFFSET ?""",
        (user_id, limit, offset)
    )
    rows = await cursor.fetchall()
    
    analyses = [
        AnalysisHistory(
            id=row[0],
            user_id=row[1],
            timestamp=row[2],
            skin_score=row[3],
            posture_score=row[4],
            eye_score=row[5],
            thermal_score=row[6],
            computed_score=row[7]
        )
        for row in rows
    ]
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "analyses": analyses
    }


@router.get("/daily-metrics/{user_id}")
async def get_daily_metrics(
    user_id: int,
    days: int = Query(default=7, le=90),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Get daily metrics for a user over the specified number of days.
    """
    cursor = await db.execute(
        """SELECT date, skin_score, posture_score, eye_score, 
                  thermal_score, overall_score
           FROM daily_metrics 
           WHERE user_id = ?
           ORDER BY date DESC
           LIMIT ?""",
        (user_id, days)
    )
    rows = await cursor.fetchall()
    
    return [
        {
            "date": row[0],
            "skin_score": row[1],
            "posture_score": row[2],
            "eye_score": row[3],
            "thermal_score": row[4],
            "overall_score": row[5]
        }
        for row in rows
    ]


@router.get("/jetson/health")
async def check_jetson_health():
    """Check health status of all Jetson ML services."""
    client = JetsonClient()
    health = await client.health_check()
    
    all_healthy = all(health.values())
    
    return {
        "status": "ok" if all_healthy else "degraded",
        "services": health,
        "thermal_enabled": settings.thermal_enabled
    }
