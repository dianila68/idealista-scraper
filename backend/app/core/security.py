from datetime import UTC, datetime, timedelta
from typing import Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def _make_token(sub: str, kind: Literal["access", "refresh"], expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    return jwt.encode(
        {"sub": sub, "kind": kind, "exp": expire},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def make_access_token(user_id: str) -> str:
    return _make_token(
        user_id, "access", timedelta(minutes=settings.access_token_expire_minutes)
    )


def make_refresh_token(user_id: str) -> str:
    return _make_token(
        user_id, "refresh", timedelta(days=settings.refresh_token_expire_days)
    )


def decode_token(token: str, expected_kind: Literal["access", "refresh"]) -> str:
    """Return the user id (sub) or raise JWTError."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    if payload.get("kind") != expected_kind:
        raise JWTError("wrong token kind")
    sub: str = payload["sub"]
    return sub
