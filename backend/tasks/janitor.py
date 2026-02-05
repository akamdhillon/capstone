# =============================================================================
# CLARITY+ BACKEND - JANITOR BACKGROUND TASK
# =============================================================================
"""
Janitor task for automatic cleanup of old image caches.
Runs daily to prune raw images older than 30 days.
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import get_settings

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    """Get or create the background scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def start_scheduler() -> None:
    """
    Start the background scheduler with Janitor task.
    
    Janitor runs daily at the configured hour (default: 2:00 AM)
    to clean up old image cache files.
    """
    settings = get_settings()
    scheduler = get_scheduler()
    
    # Add Janitor job - runs daily at configured hour
    scheduler.add_job(
        run_janitor_cleanup,
        trigger=CronTrigger(hour=settings.janitor_schedule_hour, minute=0),
        id="janitor_cleanup",
        name="Image Cache Cleanup",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(
        f"Janitor scheduled to run daily at {settings.janitor_schedule_hour:02d}:00 "
        f"(retention: {settings.image_retention_days} days)"
    )


def shutdown_scheduler() -> None:
    """Gracefully shutdown the background scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Background scheduler shutdown complete")


def run_janitor_cleanup() -> dict:
    """
    Run the Janitor cleanup task.
    
    Operations:
    1. Find and delete image cache files older than retention period
    2. Remove corresponding database records
    3. Log cleanup statistics
    
    Returns:
        Dict with cleanup statistics
    """
    settings = get_settings()
    retention_days = settings.image_retention_days
    db_path = settings.database_url.replace("sqlite:///", "")
    
    logger.info(f"Janitor starting cleanup (retention: {retention_days} days)")
    
    stats = {
        "files_deleted": 0,
        "bytes_freed": 0,
        "db_records_deleted": 0,
        "errors": []
    }
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    cutoff_iso = cutoff_date.isoformat()
    
    try:
        # Connect to database (sync version for background task)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find old image cache entries
        cursor.execute(
            "SELECT id, file_path FROM image_cache WHERE created_at < ?",
            (cutoff_iso,)
        )
        old_entries = cursor.fetchall()
        
        if not old_entries:
            logger.info("Janitor: No old images to clean up")
            conn.close()
            return stats
        
        # Delete files and collect IDs to remove from DB
        ids_to_delete = []
        
        for entry_id, file_path in old_entries:
            try:
                path = Path(file_path)
                if path.exists():
                    file_size = path.stat().st_size
                    path.unlink()
                    stats["files_deleted"] += 1
                    stats["bytes_freed"] += file_size
                    logger.debug(f"Deleted: {file_path}")
                
                ids_to_delete.append(entry_id)
                
            except OSError as e:
                error_msg = f"Failed to delete {file_path}: {e}"
                logger.warning(error_msg)
                stats["errors"].append(error_msg)
        
        # Remove database records
        if ids_to_delete:
            placeholders = ",".join("?" * len(ids_to_delete))
            cursor.execute(
                f"DELETE FROM image_cache WHERE id IN ({placeholders})",
                ids_to_delete
            )
            stats["db_records_deleted"] = cursor.rowcount
            conn.commit()
        
        conn.close()
        
        # Log summary
        mb_freed = stats["bytes_freed"] / (1024 * 1024)
        logger.info(
            f"Janitor cleanup complete: {stats['files_deleted']} files deleted, "
            f"{mb_freed:.2f} MB freed, {stats['db_records_deleted']} DB records removed"
        )
        
        if stats["errors"]:
            logger.warning(f"Janitor encountered {len(stats['errors'])} errors")
        
    except Exception as e:
        error_msg = f"Janitor cleanup failed: {e}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)
    
    return stats


async def register_image_cache(file_path: str) -> None:
    """
    Register an image file in the cache tracking table.
    Called when new images are captured.
    
    Args:
        file_path: Absolute path to the cached image
    """
    import aiosqlite
    from database.connection import get_connection
    
    try:
        conn = await get_connection()
        await conn.execute(
            "INSERT OR IGNORE INTO image_cache (file_path) VALUES (?)",
            (file_path,)
        )
        await conn.commit()
        logger.debug(f"Registered image cache: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to register image cache: {e}")


def get_cleanup_stats() -> dict:
    """
    Get current cleanup statistics and predictions.
    
    Returns:
        Dict with cache size info and next cleanup time
    """
    settings = get_settings()
    db_path = settings.database_url.replace("sqlite:///", "")
    
    stats = {
        "total_cached_files": 0,
        "total_cached_bytes": 0,
        "files_pending_cleanup": 0,
        "next_cleanup": None
    }
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Total cached files
        cursor.execute("SELECT COUNT(*) FROM image_cache")
        stats["total_cached_files"] = cursor.fetchone()[0]
        
        # Files pending cleanup (older than retention)
        cutoff = (datetime.now() - timedelta(days=settings.image_retention_days)).isoformat()
        cursor.execute(
            "SELECT COUNT(*) FROM image_cache WHERE created_at < ?",
            (cutoff,)
        )
        stats["files_pending_cleanup"] = cursor.fetchone()[0]
        
        conn.close()
        
        # Next scheduled cleanup
        scheduler = get_scheduler()
        if scheduler.running:
            job = scheduler.get_job("janitor_cleanup")
            if job:
                stats["next_cleanup"] = job.next_run_time.isoformat()
    
    except Exception as e:
        logger.warning(f"Failed to get cleanup stats: {e}")
    
    return stats
