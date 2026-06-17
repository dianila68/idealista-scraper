from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator

Platform = Literal["idealista", "immobiliare", "subito"]
LoginStatus = Literal["pending", "ok", "failed", "expired"]


class CredentialUpsert(BaseModel):
    """Request body for storing/updating platform credentials."""
    username: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("password cannot be empty")
        return v


class CredentialStatus(BaseModel):
    """Public response — never exposes username/password."""
    platform: Platform
    login_status: LoginStatus
    last_login_at: datetime | None
    cookies_expire_at: datetime | None

    model_config = {"from_attributes": True}


class VerifyResult(BaseModel):
    platform: Platform
    login_status: LoginStatus
    message: str
