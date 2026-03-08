import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from Database_files.models import User
from User.schemas import UserCreate, UserUpdate

import hashlib
import secrets

def hash_password(plain: str) -> str:
    # Use PBKDF2-HMAC-SHA256 (built into Python, no passlib/bcrypt bugs)
    salt = secrets.token_hex(16)
    # 600,000 iterations is the OWASP recommendation for PBKDF2-HMAC-SHA256 as of 2023
    key = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt.encode("utf-8"), 600_000
    )
    return f"pbkdf2_sha256$600000${salt}${key.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        algo, iters_str, salt, key_hex = hashed.split("$")
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters_str)
        key = hashlib.pbkdf2_hmac(
            "sha256", plain.encode("utf-8"), salt.encode("utf-8"), iters
        )
        return secrets.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


# ── Auth ─────────────────────────────────────────────────────────────────────

def signin(db: Session, email: str, password: str) -> User:
    """Validate credentials and return the User. Raises 401 on failure."""
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    """Verify the current password then update to a new bcrypt hash."""
    if not verify_password(current_password, user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    user.password = hash_password(new_password)
    db.commit()


# ── Create ───────────────────────────────────────────────────────────────────

def create_user(db: Session, data: UserCreate) -> User:
    # Check for duplicate email
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")

    user = User(
        name=data.name,
        email=data.email,
        password=hash_password(data.password),
        phone_num=data.phone_num,
        location=data.location,
        bio=data.bio,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Read ─────────────────────────────────────────────────────────────────────

def get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.query(User).filter(User.uuid == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


def get_all_users(db: Session, skip: int = 0, limit: int = 20) -> list[User]:
    return db.query(User).offset(skip).limit(limit).all()


# ── Update ───────────────────────────────────────────────────────────────────

def update_user(db: Session, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = get_user(db, user_id)
    updated_fields = data.model_dump(exclude_unset=True)
    for field, value in updated_fields.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


# ── Delete ───────────────────────────────────────────────────────────────────

def delete_user(db: Session, user_id: uuid.UUID) -> None:
    user = get_user(db, user_id)
    db.delete(user)
    db.commit()
