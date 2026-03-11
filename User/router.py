"""User CRUD router — admin/internal user management endpoints."""

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from Database_files.database import get_db
from User.schemas import UserUpdate, UserResponse
import User.service as service

router = APIRouter(prefix="/users", tags=["Users"])


# ── Read ─────────────────────────────────────────────────────────────────────

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve a single user by UUID."""
    return service.get_user(db, user_id)


@router.get("/", response_model=List[UserResponse])
def list_users(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """List all users with pagination (skip / limit)."""
    return service.get_all_users(db, skip, limit)


# ── Update ───────────────────────────────────────────────────────────────────

@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: uuid.UUID, data: UserUpdate, db: Session = Depends(get_db)):
    """Partially update a user's profile (only supplied fields are changed)."""
    return service.update_user(db, user_id, data)


# ── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """Permanently delete a user."""
    service.delete_user(db, user_id)
