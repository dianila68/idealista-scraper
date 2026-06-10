from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RawListing(BaseModel):
    """Internal schema produced by every scraper adapter."""

    source: str
    source_id: str
    url: str
    title: str | None = None
    price: float | None = None
    currency: str = "EUR"
    listing_type: str | None = None
    property_type: str | None = None
    city: str | None = None
    zone: str | None = None
    size_sqm: float | None = None
    rooms: int | None = None
    bathrooms: int | None = None
    floor: int | None = None
    total_floors: int | None = None
    features: list[str] = []
    images: list[str] = []
    raw: dict = {}
    published_at: datetime | None = None


class ListingResponse(BaseModel):
    """Public listing shape returned by the API."""

    id: UUID
    source: str
    source_id: str
    url: str
    title: str | None
    price: float | None
    currency: str
    listing_type: str | None
    property_type: str | None
    city: str | None
    zone: str | None
    size_sqm: float | None
    rooms: int | None
    bathrooms: int | None
    floor: int | None
    total_floors: int | None
    features: list[str]
    images: list[str]
    published_at: datetime | None
    scraped_at: datetime
    content_hash: str

    model_config = {"from_attributes": True}


class ListingDetailResponse(ListingResponse):
    """Extended response including the raw platform payload (authenticated only)."""

    raw: dict

    model_config = {"from_attributes": True}


class ListingPage(BaseModel):
    results: list[ListingResponse]
    suggestions: list[ListingResponse] = []
    total_count: int
    next_cursor: str | None
    has_more: bool


class SourceStatus(BaseModel):
    source: str
    last_scraped_at: datetime | None
    listing_count: int
    is_healthy: bool
