# =============================================================================
# CLARITY+ BACKEND - USER ROUTES
# =============================================================================
"""
API routes for user management operations.
Handles user creation, retrieval, and profile statistics.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

import aiosqlite

from database.connection import get_db
from database.models import UserCreate, User, UserWithStats
from database.encryption import encrypt_embedding, decrypt_embedding
from services.gamification import GamificationService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/users", response_model=User)
async def create_user(
    user: UserCreate,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Create a new user with optional face embedding.
    
    Face embeddings are encrypted using AES-256-GCM before storage.
    """
    # Insert user
    cursor = await db.execute(
        "INSERT INTO users (name) VALUES (?)",
        (user.name,)
    )
    user_id = cursor.lastrowid
    
    # Store encrypted face embedding if provided
    if user.face_embedding:
        ciphertext, iv, tag = encrypt_embedding(user.face_embedding)
        await db.execute(
            "INSERT INTO face_embeddings (user_id, embedding_encrypted, iv, tag) VALUES (?, ?, ?, ?)",
            (user_id, ciphertext, iv, tag)
        )
    
    # Initialize streak record
    await db.execute(
        "INSERT INTO streaks (user_id, current_streak, longest_streak) VALUES (?, 0, 0)",
        (user_id,)
    )
    
    await db.commit()
    
    # Fetch created user
    cursor = await db.execute(
        "SELECT id, name, created_at, updated_at FROM users WHERE id = ?",
        (user_id,)
    )
    row = await cursor.fetchone()
    
    logger.info(f"Created user: {user.name} (id={user_id})")
    
    return User(
        id=row[0],
        name=row[1],
        created_at=row[2],
        updated_at=row[3]
    )


@router.get("/users/{user_id}", response_model=User)
async def get_user(
    user_id: int,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Get a user by ID."""
    cursor = await db.execute(
        "SELECT id, name, created_at, updated_at FROM users WHERE id = ?",
        (user_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    return User(
        id=row[0],
        name=row[1],
        created_at=row[2],
        updated_at=row[3]
    )


@router.get("/users/{user_id}/stats", response_model=UserWithStats)
async def get_user_stats(
    user_id: int,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Get user with complete statistics including streaks and badges.
    """
    # Get user info
    cursor = await db.execute(
        "SELECT id, name, created_at, updated_at FROM users WHERE id = ?",
        (user_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = User(
        id=row[0],
        name=row[1],
        created_at=row[2],
        updated_at=row[3]
    )
    
    # Get streak info
    gamification = GamificationService(db)
    streak_info = await gamification.get_streak_info(user_id)
    
    # Get badges
    badges = await gamification.get_user_badges(user_id)
    
    # Get total analyses count
    cursor = await db.execute(
        "SELECT COUNT(*) FROM analysis_history WHERE user_id = ?",
        (user_id,)
    )
    total_analyses = (await cursor.fetchone())[0]
    
    return UserWithStats(
        id=user.id,
        name=user.name,
        created_at=user.created_at,
        updated_at=user.updated_at,
        current_streak=streak_info["current_streak"],
        longest_streak=streak_info["longest_streak"],
        total_analyses=total_analyses,
        badges=badges
    )


@router.get("/users")
async def list_users(
    db: aiosqlite.Connection = Depends(get_db)
):
    """List all users."""
    cursor = await db.execute(
        "SELECT id, name, created_at, updated_at FROM users ORDER BY created_at DESC"
    )
    rows = await cursor.fetchall()
    
    return [
        User(
            id=row[0],
            name=row[1],
            created_at=row[2],
            updated_at=row[3]
        )
        for row in rows
    ]


@router.put("/users/{user_id}/embedding")
async def update_face_embedding(
    user_id: int,
    embedding: list[float],
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Update or add face embedding for a user.
    Replaces any existing embedding.
    """
    # Verify user exists
    cursor = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="User not found")
    
    # Encrypt new embedding
    ciphertext, iv, tag = encrypt_embedding(embedding)
    
    # Delete existing embedding if any
    await db.execute(
        "DELETE FROM face_embeddings WHERE user_id = ?",
        (user_id,)
    )
    
    # Insert new embedding
    await db.execute(
        "INSERT INTO face_embeddings (user_id, embedding_encrypted, iv, tag) VALUES (?, ?, ?, ?)",
        (user_id, ciphertext, iv, tag)
    )
    
    await db.commit()
    
    logger.info(f"Updated face embedding for user {user_id}")
    
    return {"message": "Face embedding updated successfully"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Delete a user and all associated data.
    This includes embeddings, analysis history, streaks, and badges.
    """
    # Verify user exists
    cursor = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete user (cascades to related tables)
    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    await db.commit()
    
    logger.info(f"Deleted user {user_id}")
    
    return {"message": "User deleted successfully"}
