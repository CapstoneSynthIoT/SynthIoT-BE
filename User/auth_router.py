"""Authentication router — public and protected auth endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from Database_files.database import get_db
from Database_files.models import User
from User.schemas import (
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse,
    ChangePasswordRequest,
)
from User.auth import create_access_token, get_current_user
import User.service as service

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Sign up ───────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user. Password is stored as a bcrypt hash."""
    return service.create_user(db, data)


# ── Sign in ───────────────────────────────────────────────────────────────────

@router.post("/signin", response_model=TokenResponse)
def signin(data: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email + password. Returns a JWT access token."""
    user = service.signin(db, data.email, data.password)
    token = create_access_token(user.uuid)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


# ── Change password ───────────────────────────────────────────────────────────

@router.put("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change the authenticated user's password.

    Requires a valid Bearer token in the Authorization header.
    Verifies the current password before applying the new one.
    """
    service.change_password(db, current_user, data.current_password, data.new_password)


# ── Me (convenience) ──────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user
