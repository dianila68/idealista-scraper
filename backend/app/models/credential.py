from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid

VALID_PLATFORMS = frozenset({"idealista", "immobiliare", "subito"})
VALID_STATUSES = frozenset({"pending", "ok", "failed", "expired"})


class PlatformCredential(Base, TimestampMixin):
    __tablename__ = "platform_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", name="uq_platform_credentials_user_platform"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)

    # Fernet-encrypted — never log or expose raw values
    username_enc: Mapped[str] = mapped_column(Text, nullable=False)
    password_enc: Mapped[str] = mapped_column(Text, nullable=False)

    # Encrypted JSON cookie jar; populated after first successful login
    cookies_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    cookies_expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    login_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
