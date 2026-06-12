"""M8 unit tests — email service, auth flows, profile update (all mocked)."""
import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.user import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UpdateProfileRequest,
    UserLogin,
)
from app.services.email import send_password_reset_email, send_verification_email

# ── Email service ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_verification_email_calls_smtp():
    with patch("app.services.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await send_verification_email("user@example.com", "http://localhost/verify?token=abc")
    mock_send.assert_awaited_once()
    call_kwargs = mock_send.call_args
    msg = call_kwargs[0][0]
    assert msg["To"] == "user@example.com"
    assert "verifica" in msg["Subject"].lower()


@pytest.mark.asyncio
async def test_send_reset_email_calls_smtp():
    with patch("app.services.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await send_password_reset_email("user@example.com", "http://localhost/reset?token=xyz")
    mock_send.assert_awaited_once()
    msg = mock_send.call_args[0][0]
    assert msg["To"] == "user@example.com"
    assert "password" in msg["Subject"].lower()


@pytest.mark.asyncio
async def test_send_email_smtp_error_does_not_raise():
    with patch("app.services.email.aiosmtplib.send", side_effect=Exception("SMTP down")):
        # Should log and swallow, not raise
        await send_verification_email("user@example.com", "http://example.com/v")


# ── is_verified enforcement ───────────────────────────────────────────────────

def _make_user(is_verified: bool = True, is_active: bool = True) -> MagicMock:
    u = MagicMock()
    u.id = "user-uuid"
    u.email = "test@example.com"
    u.hashed_password = "$2b$12$fake"
    u.is_verified = is_verified
    u.is_active = is_active
    u.password_reset_token = None
    u.password_reset_expires = None
    return u


def _mock_db(user: object = None) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_login_unverified_returns_403():
    from app.api.v1.auth import login
    from app.core.security import hash_password

    user = _make_user(is_verified=False)
    user.hashed_password = hash_password("password123")
    db = _mock_db(user=user)

    with pytest.raises(Exception) as exc_info:
        await login(UserLogin(email="test@example.com", password="password123"), db=db)
    assert exc_info.value.status_code == 403
    assert "verified" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_login_verified_returns_tokens():
    from app.api.v1.auth import login
    from app.core.security import hash_password

    user = _make_user(is_verified=True)
    user.hashed_password = hash_password("password123")
    db = _mock_db(user=user)

    result = await login(UserLogin(email="test@example.com", password="password123"), db=db)
    assert result.access_token
    assert result.refresh_token


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401():
    from app.api.v1.auth import login
    from app.core.security import hash_password

    user = _make_user(is_verified=True)
    user.hashed_password = hash_password("correct-password")
    db = _mock_db(user=user)

    with pytest.raises(Exception) as exc_info:
        await login(UserLogin(email="test@example.com", password="wrong-password"), db=db)
    assert exc_info.value.status_code == 401


# ── Forgot / reset password ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forgot_password_sends_email_for_known_user():
    from app.api.v1.auth import forgot_password

    user = _make_user()
    db = _mock_db(user=user)

    with patch("app.api.v1.auth.send_password_reset_email", new_callable=AsyncMock) as mock_mail:
        resp = await forgot_password(ForgotPasswordRequest(email="test@example.com"), db=db)

    assert resp["message"]
    mock_mail.assert_awaited_once()


@pytest.mark.asyncio
async def test_forgot_password_silent_for_unknown_email():
    """No error and no email sent when email doesn't exist."""
    from app.api.v1.auth import forgot_password

    db = _mock_db(user=None)
    with patch("app.api.v1.auth.send_password_reset_email", new_callable=AsyncMock) as mock_mail:
        resp = await forgot_password(ForgotPasswordRequest(email="nobody@example.com"), db=db)

    assert resp["message"]
    mock_mail.assert_not_awaited()


@pytest.mark.asyncio
async def test_reset_password_valid_token_updates_hash():
    from app.api.v1.auth import reset_password

    token = secrets.token_urlsafe(32)
    user = _make_user()
    user.password_reset_token = token
    user.password_reset_expires = datetime.now(UTC) + timedelta(hours=1)
    db = _mock_db(user=user)

    resp = await reset_password(
        ResetPasswordRequest(token=token, new_password="newpassword99"), db=db
    )
    assert "updated" in resp["message"].lower()
    assert user.password_reset_token is None


@pytest.mark.asyncio
async def test_reset_password_expired_token_returns_400():
    from app.api.v1.auth import reset_password

    db = _mock_db(user=None)  # expired → DB returns None
    with pytest.raises(Exception) as exc_info:
        await reset_password(
            ResetPasswordRequest(token="expired-token", new_password="newpassword99"), db=db
        )
    assert exc_info.value.status_code == 400


# ── Profile update ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_profile_timezone():
    from app.api.v1.users import update_me
    from app.core.security import hash_password

    user = _make_user()
    user.timezone = "Europe/Rome"
    user.hashed_password = hash_password("pass1234")
    user.filters = []
    user.devices = []

    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.scalar = AsyncMock(return_value=0)

    with patch("app.api.v1.users.UserResponse.model_validate", return_value=MagicMock(filter_count=0, device_count=0)):
        await update_me(UpdateProfileRequest(timezone="Europe/London"), user=user, db=db)

    assert user.timezone == "Europe/London"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_profile_password_change():
    from app.api.v1.users import update_me
    from app.core.security import hash_password
    from app.core.security import verify_password as _verify

    user = _make_user()
    user.hashed_password = hash_password("oldpass99")
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.scalar = AsyncMock(return_value=0)

    with patch("app.api.v1.users.UserResponse.model_validate", return_value=MagicMock(filter_count=0, device_count=0)):
        await update_me(
            UpdateProfileRequest(current_password="oldpass99", new_password="newpass99"),
            user=user, db=db,
        )

    assert _verify("newpass99", user.hashed_password)


@pytest.mark.asyncio
async def test_update_profile_wrong_current_password_raises():
    from app.api.v1.users import update_me
    from app.core.security import hash_password

    user = _make_user()
    user.hashed_password = hash_password("correct99")
    db = AsyncMock()

    with pytest.raises(Exception) as exc_info:
        await update_me(
            UpdateProfileRequest(current_password="wrong999", new_password="newpass99"),
            user=user, db=db,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_update_profile_new_password_without_current_raises():
    from app.api.v1.users import update_me

    user = _make_user()
    db = AsyncMock()

    with pytest.raises(Exception) as exc_info:
        await update_me(
            UpdateProfileRequest(new_password="newpass99"),  # no current_password
            user=user, db=db,
        )
    assert exc_info.value.status_code == 422
