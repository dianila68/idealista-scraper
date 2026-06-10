from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PriceRange(BaseModel):
    min: float | None = None
    max: float | None = None


class SizeRange(BaseModel):
    min: float | None = None
    max: float | None = None


class RoomRange(BaseModel):
    min: int | None = None
    max: int | None = None


class FloorFilter(BaseModel):
    min: int | None = None
    exclude_ground: bool = False


class LocationFilter(BaseModel):
    city: str
    zones: list[str] = []


class FilterConfig(BaseModel):
    """The platform-agnostic filter model. All fields optional."""

    listing_type: Literal["rent", "sale"] | None = None
    property_type: list[str] | None = None
    locations: list[LocationFilter] = []
    price: PriceRange = Field(default_factory=PriceRange)
    size_sqm: SizeRange = Field(default_factory=SizeRange)
    rooms: RoomRange = Field(default_factory=RoomRange)
    bathrooms: RoomRange = Field(default_factory=RoomRange)
    floor: FloorFilter = Field(default_factory=FloorFilter)
    features: list[str] = []
    exclude_agencies: bool = False
    sources: list[Literal["idealista", "immobiliare", "subito"]] = [
        "idealista",
        "immobiliare",
        "subito",
    ]


class FilterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    config: FilterConfig
    notify: bool = True
    notify_digest: bool = False


class FilterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: FilterConfig | None = None
    notify: bool | None = None
    notify_digest: bool | None = None


class FilterResponse(BaseModel):
    id: UUID
    name: str
    config: FilterConfig
    notify: bool
    notify_digest: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
