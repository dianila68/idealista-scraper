"""platform_credentials table

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-03 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        # Fernet-encrypted fields — plaintext credentials never stored
        sa.Column("username_enc", sa.Text(), nullable=False),
        sa.Column("password_enc", sa.Text(), nullable=False),
        # Encrypted JSON cookie jar (dict of name→value), nullable until first login
        sa.Column("cookies_enc", sa.Text(), nullable=True),
        sa.Column("cookies_expire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("login_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "platform", name="uq_platform_credentials_user_platform"),
    )
    op.create_index("ix_platform_credentials_user_id", "platform_credentials", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_platform_credentials_user_id", table_name="platform_credentials")
    op.drop_table("platform_credentials")
