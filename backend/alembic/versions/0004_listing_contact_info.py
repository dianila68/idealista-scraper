"""add contact info columns to listings

Revision ID: 0004
Revises: 0003
Create Date: 2024-01-04 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # contact_phone and contact_email are only populated when the scraper
    # runs authenticated (user has connected their platform account).
    op.add_column("listings", sa.Column("contact_phone", sa.String(64), nullable=True))
    op.add_column("listings", sa.Column("contact_email", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("listings", "contact_email")
    op.drop_column("listings", "contact_phone")
