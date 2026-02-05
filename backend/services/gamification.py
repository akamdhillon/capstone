# =============================================================================
# CLARITY+ BACKEND - GAMIFICATION SERVICE
# =============================================================================
"""
Gamification service for streaks and badge management.
Implements engagement mechanics to encourage consistent usage.
"""

import logging
from datetime import date, timedelta
from typing import Optional

import aiosqlite

from database.models import BadgeType

logger = logging.getLogger(__name__)


class GamificationService:
    """
    Gamification service managing streaks and badges.
    
    Streaks:
    - Incremented for each consecutive day of use
    - Reset if a day is skipped
    
    Badges:
    - "Posture Pro": 7 consecutive days with posture score >= 80
    - "Consistent Glow": 30 days with skin score >= 75
    - "First Scan": First analysis completed
    - "Week Warrior": 7-day streak achieved
    - "Month Master": 30-day streak achieved
    """
    
    def __init__(self, db: aiosqlite.Connection):
        self.db = db
    
    async def update_streak(self, user_id: int) -> tuple[int, int]:
        """
        Update user's streak based on today's activity.
        
        Args:
            user_id: The user to update
            
        Returns:
            Tuple of (current_streak, longest_streak)
        """
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # Get current streak info
        cursor = await self.db.execute(
            "SELECT current_streak, longest_streak, last_active_date FROM streaks WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        
        if row is None:
            # First time user - create streak record
            await self.db.execute(
                "INSERT INTO streaks (user_id, current_streak, longest_streak, last_active_date) VALUES (?, 1, 1, ?)",
                (user_id, today.isoformat())
            )
            await self.db.commit()
            
            # Award first scan badge
            await self._award_badge(user_id, BadgeType.FIRST_SCAN)
            
            return 1, 1
        
        current_streak = row[0]
        longest_streak = row[1]
        last_active = row[2]
        
        # Parse last active date
        if last_active:
            if isinstance(last_active, str):
                last_active_date = date.fromisoformat(last_active)
            else:
                last_active_date = last_active
        else:
            last_active_date = None
        
        # Already logged today
        if last_active_date == today:
            return current_streak, longest_streak
        
        # Continue streak if last active was yesterday
        if last_active_date == yesterday:
            current_streak += 1
        else:
            # Streak broken - restart
            current_streak = 1
        
        # Update longest streak if needed
        if current_streak > longest_streak:
            longest_streak = current_streak
        
        # Save updated streak
        await self.db.execute(
            """UPDATE streaks 
               SET current_streak = ?, longest_streak = ?, last_active_date = ?
               WHERE user_id = ?""",
            (current_streak, longest_streak, today.isoformat(), user_id)
        )
        await self.db.commit()
        
        # Check for streak badges
        if current_streak >= 7:
            await self._award_badge(user_id, BadgeType.WEEK_WARRIOR)
        if current_streak >= 30:
            await self._award_badge(user_id, BadgeType.MONTH_MASTER)
        
        logger.info(f"User {user_id} streak updated: {current_streak} (longest: {longest_streak})")
        
        return current_streak, longest_streak
    
    async def check_performance_badges(
        self,
        user_id: int,
        skin_score: Optional[float] = None,
        posture_score: Optional[float] = None
    ) -> list[str]:
        """
        Check and award performance-based badges.
        
        Args:
            user_id: The user to check
            skin_score: Today's skin score
            posture_score: Today's posture score
            
        Returns:
            List of newly awarded badge types
        """
        awarded = []
        
        # Check Posture Pro - 7 consecutive days with posture >= 80
        if posture_score and posture_score >= 80:
            days = await self._count_consecutive_days(
                user_id, "posture_score", 80
            )
            if days >= 7:
                if await self._award_badge(user_id, BadgeType.POSTURE_PRO):
                    awarded.append(BadgeType.POSTURE_PRO)
        
        # Check Consistent Glow - 30 days with skin >= 75
        if skin_score and skin_score >= 75:
            days = await self._count_total_days(
                user_id, "skin_score", 75
            )
            if days >= 30:
                if await self._award_badge(user_id, BadgeType.CONSISTENT_GLOW):
                    awarded.append(BadgeType.CONSISTENT_GLOW)
        
        return awarded
    
    async def _count_consecutive_days(
        self,
        user_id: int,
        score_column: str,
        min_score: float
    ) -> int:
        """Count consecutive days meeting score threshold."""
        cursor = await self.db.execute(
            f"""SELECT date FROM daily_metrics 
                WHERE user_id = ? AND {score_column} >= ?
                ORDER BY date DESC""",
            (user_id, min_score)
        )
        rows = await cursor.fetchall()
        
        if not rows:
            return 0
        
        consecutive = 0
        expected_date = date.today()
        
        for row in rows:
            row_date = row[0]
            if isinstance(row_date, str):
                row_date = date.fromisoformat(row_date)
            
            if row_date == expected_date:
                consecutive += 1
                expected_date -= timedelta(days=1)
            else:
                break
        
        return consecutive
    
    async def _count_total_days(
        self,
        user_id: int,
        score_column: str,
        min_score: float
    ) -> int:
        """Count total days meeting score threshold."""
        cursor = await self.db.execute(
            f"""SELECT COUNT(*) FROM daily_metrics 
                WHERE user_id = ? AND {score_column} >= ?""",
            (user_id, min_score)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
    
    async def _award_badge(self, user_id: int, badge_type: str) -> bool:
        """
        Award a badge to a user if not already earned.
        
        Returns:
            True if badge was newly awarded, False if already had it
        """
        try:
            await self.db.execute(
                "INSERT INTO badges (user_id, badge_type) VALUES (?, ?)",
                (user_id, badge_type)
            )
            await self.db.commit()
            logger.info(f"Badge '{badge_type}' awarded to user {user_id}")
            return True
        except aiosqlite.IntegrityError:
            # Badge already exists
            return False
    
    async def get_user_badges(self, user_id: int) -> list[str]:
        """Get all badges for a user."""
        cursor = await self.db.execute(
            "SELECT badge_type FROM badges WHERE user_id = ? ORDER BY awarded_at",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
    
    async def get_streak_info(self, user_id: int) -> dict:
        """Get streak information for a user."""
        cursor = await self.db.execute(
            "SELECT current_streak, longest_streak, last_active_date FROM streaks WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        
        if row is None:
            return {
                "current_streak": 0,
                "longest_streak": 0,
                "last_active_date": None
            }
        
        return {
            "current_streak": row[0],
            "longest_streak": row[1],
            "last_active_date": row[2]
        }
