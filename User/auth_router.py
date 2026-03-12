"""Authentication router — public and protected auth endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from Database_files.database import get_db
from Database_files.models import User
from User.schemas import (
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse,
    ChangePasswordRequest,
    ResetPasswordRequest,
    OTPRequest,
    OTPVerify,
    VerificationTokenResponse,
)
from User.auth import create_access_token, get_current_user
from User.email_otp import (
    generate_otp,
    verify_otp,
    send_otp_email,
    create_verification_token,
    verify_verification_token,
)
import User.service as service

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Email OTP — Step 1: Request OTP ──────────────────────────────────────────

@router.post("/request-otp", status_code=status.HTTP_200_OK)
def request_otp(data: OTPRequest):
    """
    Send a 6-digit OTP to the given email address.

    Call this before signing up. The OTP is valid for ~5 minutes.
    No database storage is used — the OTP is derived from an HMAC of the
    server secret + email + current time window.
    """
    otp = generate_otp(data.email)
    send_otp_email(data.email, otp)
    return {"message": f"OTP sent to {data.email}. Please check your inbox."}


# ── Email OTP — Step 2: Verify OTP ────────────────────────────────────────────

@router.post("/verify-otp", response_model=VerificationTokenResponse)
def verify_otp_endpoint(data: OTPVerify):
    """
    Verify the OTP received by email.

    On success, returns a short-lived `verification_token` (valid for
    OTP_EXPIRE_MINUTES, default 10 min). Pass this token in the signup request.
    On failure, returns 400 Bad Request.
    """
    if not verify_otp(data.email, data.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please request a new one.",
        )

    token = create_verification_token(data.email)
    return VerificationTokenResponse(
        verification_token=token,
        message="Email verified successfully. Use the verification_token to complete signup.",
    )


# ── Sign up (requires prior email verification) ───────────────────────────────

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.

    Requires a valid `verification_token` obtained from POST /auth/verify-otp.
    The token must correspond to the same email address used in this request.
    Password is stored as a bcrypt hash.
    """
    # 1. Validate the verification token and extract the verified email
    verified_email = verify_verification_token(data.verification_token)

    # 2. Ensure the token's email matches the signup email (prevent token reuse)
    if verified_email.lower() != data.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token does not match the provided email address.",
        )

    # 3. Create the user
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


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Reset password using a verification token.
    The token must have been obtained by verifying an OTP for this email.
    """
    # 1. Validate the verification token
    verified_email = verify_verification_token(data.verification_token)

    # 2. Match email
    if verified_email.lower() != data.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token does not match the provided email address.",
        )

    # 3. Update password
    service.reset_password(db, data.email, data.new_password)
    return {"message": "Password reset successfully."}


# ── Me (convenience) ──────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user
