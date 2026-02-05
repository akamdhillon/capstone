# =============================================================================
# CLARITY+ BACKEND - DATABASE CONNECTION
# =============================================================================
"""
Async SQLite database connection management using aiosqlite.
"""

import aiosqlite
import os
from pathlib import Path
from typing import AsyncGenerator

from config import get_settings

settings = get_settings()

# Extract database path from URL
_db_path = settings.database_url.replace("sqlite:///", "")
DATABASE_PATH = Path(_db_path)

# Global connection reference
_connection: aiosqlite.Connection | None = None


async def get_connection() -> aiosqlite.Connection:
    """Get or create database connection."""
    global _connection
    if _connection is None:
        # Ensure data directory exists
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _connection = await aiosqlite.connect(DATABASE_PATH)
        _connection.row_factory = aiosqlite.Row
    return _connection


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Dependency injection for database connection.
    Usage: db: aiosqlite.Connection = Depends(get_db)
    """
    conn = await get_connection()
    try:
        yield conn
    finally:
        pass  # Connection is managed by lifespan


async def init_database() -> None:
    """
    Initialize database schema.
    Creates all tables if they don't exist.
    """
    conn = await get_connection()
    
    # Users table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Face embeddings with encrypted data
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS face_embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            embedding_encrypted BLOB NOT NULL,
            iv BLOB NOT NULL,
            tag BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Daily aggregated metrics
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            skin_score REAL,
            posture_score REAL,
            eye_score REAL,
            thermal_score REAL,
            overall_score REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(user_id, date)
        )
    """)
    
    # Individual analysis history
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            raw_results TEXT NOT NULL,
            skin_score REAL,
            posture_score REAL,
            eye_score REAL,
            thermal_score REAL,
            computed_score REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Streak tracking for gamification
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS streaks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0,
            last_active_date DATE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Badge achievements
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_type TEXT NOT NULL,
            awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(user_id, badge_type)
        )
    """)
    
    # Image cache tracking for Janitor
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS image_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes for performance
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_daily_metrics_user_date ON daily_metrics(user_id, date)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_history_user ON analysis_history(user_id)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_image_cache_created ON image_cache(created_at)"
    )
    
    await conn.commit()


async def close_database() -> None:
    """Close database connection."""
    global _connection
    if _connection:
        await _connection.close()
        _connection = None
