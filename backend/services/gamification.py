"""
Gamification service — future feature.

Planned capabilities:
- Streak tracking (consecutive days with at least one wellness analysis)
- Achievement badges (e.g., "First Posture Check", "7-Day Streak")
- Score trend rewards

Not yet implemented. The class is exported from the services package so
downstream code can import it without breaking when the feature ships.
"""


class GamificationService:
    """Placeholder for gamification logic. Not yet implemented."""

    def get_streak(self, user_id: str) -> int:
        """Return the current consecutive-day streak for *user_id*."""
        return 0

    def get_achievements(self, user_id: str) -> list[str]:
        """Return earned achievement badges for *user_id*."""
        return []
