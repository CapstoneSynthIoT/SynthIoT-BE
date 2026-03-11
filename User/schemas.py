import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    verification_token: str  # Must be obtained from POST /auth/verify-otp
    phone_num: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone_num: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None


class UserResponse(BaseModel):
    uuid: uuid.UUID
    name: str
    email: EmailStr
    phone_num: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ── Email OTP ─────────────────────────────────────────────────────────────────

class OTPRequest(BaseModel):
    email: EmailStr


class OTPVerify(BaseModel):
    email: EmailStr
    otp: str  # The 6-digit code received by email


class VerificationTokenResponse(BaseModel):
    verification_token: str
    message: str
