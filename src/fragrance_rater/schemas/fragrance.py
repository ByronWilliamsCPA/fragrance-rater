"""Pydantic schemas for fragrance-related API models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    """Schema for creating a new note."""

    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=50)
    subcategory: str | None = Field(None, max_length=50)


class NoteResponse(BaseModel):
    """Schema for note response."""

    id: str
    name: str
    category: str
    subcategory: str | None

    model_config = {"from_attributes": True}


class FragranceNoteCreate(BaseModel):
    """Schema for creating a fragrance-note association."""

    note_name: str = Field(..., min_length=1, max_length=100)
    note_category: str = Field(..., min_length=1, max_length=50)
    position: Literal["top", "heart", "base"]


class FragranceNoteResponse(BaseModel):
    """Schema for fragrance-note response."""

    note: NoteResponse
    position: str

    model_config = {"from_attributes": True}


class FragranceAccordCreate(BaseModel):
    """Schema for creating a fragrance accord."""

    accord_type: str = Field(..., min_length=1, max_length=50)
    intensity: float = Field(..., ge=0.0, le=1.0)


class FragranceAccordResponse(BaseModel):
    """Schema for fragrance accord response."""

    accord_type: str
    intensity: float

    model_config = {"from_attributes": True}


class FragranceCreate(BaseModel):
    """Schema for creating a new fragrance."""

    name: str = Field(..., min_length=1, max_length=255)
    brand: str = Field(..., min_length=1, max_length=255)
    concentration: str = Field(..., min_length=1, max_length=50)
    launch_year: int | None = Field(None, ge=1800, le=2100)
    gender_target: Literal["Masculine", "Feminine", "Unisex"] = "Unisex"
    primary_family: str = Field(..., min_length=1, max_length=50)
    subfamily: str = Field(..., min_length=1, max_length=50)
    intensity: str | None = Field(None, max_length=20)
    notes: list[FragranceNoteCreate] = Field(default_factory=list)
    accords: list[FragranceAccordCreate] = Field(default_factory=list)


class FragranceUpdate(BaseModel):
    """Schema for updating a fragrance."""

    name: str | None = Field(None, min_length=1, max_length=255)
    brand: str | None = Field(None, min_length=1, max_length=255)
    concentration: str | None = Field(None, min_length=1, max_length=50)
    launch_year: int | None = Field(None, ge=1800, le=2100)
    gender_target: Literal["Masculine", "Feminine", "Unisex"] | None = None
    primary_family: str | None = Field(None, min_length=1, max_length=50)
    subfamily: str | None = Field(None, min_length=1, max_length=50)
    intensity: str | None = Field(None, max_length=20)


class FragranceResponse(BaseModel):
    """Schema for fragrance response."""

    id: str
    name: str
    brand: str
    concentration: str
    launch_year: int | None
    gender_target: str
    primary_family: str
    subfamily: str
    intensity: str | None
    data_source: str
    external_id: str | None
    created_at: datetime
    updated_at: datetime
    notes: list[FragranceNoteResponse] = Field(default_factory=list)
    accords: list[FragranceAccordResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class FragranceSearchParams(BaseModel):
    """Schema for fragrance search parameters."""

    q: str | None = Field(None, description="Search query for name or brand")
    brand: str | None = Field(None, description="Filter by brand")
    primary_family: str | None = Field(None, description="Filter by fragrance family")
    gender_target: Literal["Masculine", "Feminine", "Unisex"] | None = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
