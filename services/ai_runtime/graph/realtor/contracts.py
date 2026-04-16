"""Realtor-owned business contracts.

These types are vertical-specific and must not be imported by
``services/ai_runtime/domain`` nor by other verticals' code.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DetailAttributeKey = Literal["habitaciones", "banos", "area", "precio", "garage", "foto"]


class PropertyFeatures(BaseModel):
    """Canonical normalized property feature set."""

    garage_clean: int
    bedrooms_clean: int
    bathrooms_clean: float
    sqm_clean: int | None = None
    lot_size_sqm: str | None = None
    front: str | None = None
    land_use: str | None = None
    property_type: str | None = None
    year_built: str | None = None
    amenities: list[str] = Field(default_factory=list)
    is_featured: bool = False
    size_unit: str | None = None
    garage: str | None = None
    bedrooms: str | None = None
    bathrooms: str | None = None


class PropertyMedia(BaseModel):
    primary_image_url: str | None = None
    image_urls: list[str] = Field(default_factory=list)


class PropertyLocation(BaseModel):
    country: str | None = None
    province: str | None = None
    lat: float | None = None
    lng: float | None = None


class PropertyMeta(BaseModel):
    source_system: str | None = None
    public_url: str | None = None
    ingested_at: datetime | None = None
    updated_at: datetime | None = None


class Property(BaseModel):
    """Canonical property contract v1.0."""

    model_config = ConfigDict(extra="forbid")

    id: str
    client_id: str
    title: str
    description_html: str
    price: float
    currency: str
    address: str | None = None
    features: PropertyFeatures
    media: PropertyMedia = Field(default_factory=PropertyMedia)
    location: PropertyLocation = Field(default_factory=PropertyLocation)
    meta: PropertyMeta = Field(default_factory=PropertyMeta)


class PropertyComparisonScore(BaseModel):
    property_id: str
    score_total: float
    dimensions: dict[str, float] = Field(default_factory=dict)


class CardStat(BaseModel):
    icon: str
    value: str
    label: str


class CardPayload(BaseModel):
    id: str
    title: str
    price: float
    currency: str
    bedrooms_clean: int
    bathrooms_clean: float
    sqm_clean: int | None = None
    garage_clean: int = 0
    lot_size_sqm: str | None = None
    front: str | None = None
    land_use: str | None = None
    property_type: str | None = None
    location: str | None = None
    address: str | None = None
    primary_image_url: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    photo_count: int = 0
    public_url: str | None = None
    province: str | None = None
    amenities: list[str] = Field(default_factory=list)
    description: str | None = None
    price_note: str | None = None
    badge_main: str | None = None
    badge_sub: str | None = None
    stats: list[CardStat] = Field(default_factory=list)
