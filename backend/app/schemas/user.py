from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    # No length constraints: login must not leak registration rules — any
    # wrong password should produce 401, not 422.
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    is_verified: bool
    is_active: bool
    timezone: str
    created_at: datetime
    filter_count: int = 0
    device_count: int = 0

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UpdateProfileRequest(BaseModel):
    timezone: str | None = None
    current_password: str | None = None
    new_password: str | None = Field(None, min_length=8, max_length=128)
