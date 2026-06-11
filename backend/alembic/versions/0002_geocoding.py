"""add lat/lng to listings

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("lat", sa.Numeric(9, 6), nullable=True))
    op.add_column("listings", sa.Column("lng", sa.Numeric(9, 6), nullable=True))
    op.create_index("ix_listings_lat_lng", "listings", ["lat", "lng"])


def downgrade() -> None:
    op.drop_index("ix_listings_lat_lng", table_name="listings")
    op.drop_column("listings", "lng")
    op.drop_column("listings", "lat")
