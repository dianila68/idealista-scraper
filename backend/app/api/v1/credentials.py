"""Platform credential management endpoints.

Users store their Idealista / Immobiliare / Subito credentials here.
Credentials are Fernet-encrypted before writing and never returned in plaintext.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.credential import PlatformCredential
from app.models.user import User
from app.schemas.credential import CredentialStatus, CredentialUpsert, Platform, VerifyResult
from app.services.credential_crypto import decrypt, encrypt, encrypt_cookies
from app.services.platform_auth import platform_login

log = structlog.get_logger()
router = APIRouter()

# Cookies are valid for 7 days by default before we force re-login
_COOKIE_TTL = timedelta(days=7)


def _get_row(
    rows: list[PlatformCredential],
    platform: str,
) -> PlatformCredential | None:
    return next((r for r in rows if r.platform == platform), None)


@router.put("/{platform}", status_code=status.HTTP_200_OK)
async def upsert_credentials(
    body: CredentialUpsert,
    platform: Platform = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Store or update credentials for a platform.

    Credentials are encrypted before persisting. The login is NOT performed
    immediately; use POST /{platform}/verify to trigger a live login check.
    """
    uid = str(current_user.id)
    result = await db.execute(
        select(PlatformCredential).where(
            PlatformCredential.user_id == current_user.id,
            PlatformCredential.platform == platform,
        )
    )
    row = result.scalar_one_or_none()

    username_enc = encrypt(body.username, uid, platform)
    password_enc = encrypt(body.password, uid, platform)

    if row is None:
        row = PlatformCredential(
            user_id=current_user.id,
            platform=platform,
            username_enc=username_enc,
            password_enc=password_enc,
            login_status="pending",
        )
        db.add(row)
    else:
        row.username_enc = username_enc
        row.password_enc = password_enc
        row.login_status = "pending"
        row.cookies_enc = None
        row.cookies_expire_at = None

    await db.commit()
    return {"message": f"{platform} credentials saved. Use /verify to test the login."}


@router.get("", response_model=list[CredentialStatus])
async def list_credentials(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformCredential]:
    """List platforms the user has connected. Never returns username/password."""
    result = await db.execute(
        select(PlatformCredential).where(PlatformCredential.user_id == current_user.id)
    )
    return list(result.scalars().all())


@router.delete("/{platform}")
async def delete_credentials(
    platform: Platform = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Permanently delete stored credentials for a platform."""
    result = await db.execute(
        select(PlatformCredential).where(
            PlatformCredential.user_id == current_user.id,
            PlatformCredential.platform == platform,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No credentials stored for {platform}")
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{platform}/verify", response_model=VerifyResult)
async def verify_credentials(
    platform: Platform = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyResult:
    """Immediately attempt a login with stored credentials and report status.

    On success, the resulting cookies are persisted so the next scrape run uses them.
    Idealista requires Playwright to be installed (bundled in requirements.txt).
    """
    uid = str(current_user.id)
    result = await db.execute(
        select(PlatformCredential).where(
            PlatformCredential.user_id == current_user.id,
            PlatformCredential.platform == platform,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No credentials stored for {platform}")

    username = decrypt(row.username_enc, uid, platform)
    password = decrypt(row.password_enc, uid, platform)

    try:
        cookies = await platform_login(platform, username, password)
    except Exception as exc:
        log.warning("credentials.verify.failed", platform=platform, user_id=uid, exc=str(exc))
        row.login_status = "failed"
        await db.commit()
        return VerifyResult(
            platform=platform,  # type: ignore[arg-type]
            login_status="failed",
            message=f"Login failed: {exc}",
        )

    row.cookies_enc = encrypt_cookies(cookies, uid, platform)
    row.cookies_expire_at = datetime.now(UTC) + _COOKIE_TTL
    row.login_status = "ok"
    row.last_login_at = datetime.now(UTC)
    await db.commit()

    return VerifyResult(
        platform=platform,  # type: ignore[arg-type]
        login_status="ok",
        message=f"Login successful — {len(cookies)} cookies stored, valid until {row.cookies_expire_at:%Y-%m-%d}",
    )
