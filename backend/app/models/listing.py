import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_uuid


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="EUR", nullable=False)
    listing_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    property_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_sqm: Mapped[float | None] = mapped_column(Numeric(8, 1), nullable=True)
    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    lng: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    features: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    images: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    raw: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_listings_source_source_id"),
        UniqueConstraint("source", "content_hash", name="uq_listings_source_content_hash"),
        Index("ix_listings_scraped_at_brin", "scraped_at", postgresql_using="brin"),
        Index("ix_listings_price", "price"),
        Index("ix_listings_city_zone", "city", "zone"),
    )
