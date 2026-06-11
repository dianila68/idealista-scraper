import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    decode_token,
    hash_password,
    make_access_token,
    make_refresh_token,
    verify_password,
)
from app.models.user import User
from app.schemas.user import (
    ForgotPasswordRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
)
from app.services.email import send_password_reset_email, send_verification_email

router = APIRouter()

_BASE_URL = "http://localhost:8000"  # overridden by APP_BASE_URL env var if needed


def _base_url() -> str:
    return getattr(settings, "app_base_url", _BASE_URL)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    token = secrets.token_urlsafe(32)
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        verification_token=token,
        verification_token_expires=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    verify_url = f"{_base_url()}/auth/verify?token={token}"
    await send_verification_email(user.email, verify_url)

    return {"id": str(user.id), "email": user.email, "message": "Check your email to verify your account"}


@router.post("/token", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified. Check your inbox.")
    return TokenResponse(
        access_token=make_access_token(str(user.id)),
        refresh_token=make_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        user_id = decode_token(body.refresh_token, "refresh")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    return TokenResponse(
        access_token=make_access_token(user_id),
        refresh_token=make_refresh_token(user_id),
    )


@router.get("/verify")
async def verify_email(token: str = Query(...), db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    result = await db.execute(
        select(User).where(
            User.verification_token == token,
            User.verification_token_expires > datetime.now(UTC),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    await db.commit()
    return {"message": "Email verified"}


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    # Always return 202 — don't leak whether the email exists
    if user and user.is_active:
        token = secrets.token_urlsafe(32)
        user.password_reset_token = token
        user.password_reset_expires = datetime.now(UTC) + timedelta(hours=1)
        await db.commit()
        reset_url = f"{_base_url()}/auth/reset-password?token={token}"
        await send_password_reset_email(user.email, reset_url)
    return {"message": "If that email exists you will receive a reset link shortly"}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    result = await db.execute(
        select(User).where(
            User.password_reset_token == body.token,
            User.password_reset_expires > datetime.now(UTC),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    await db.commit()
    return {"message": "Password updated"}
