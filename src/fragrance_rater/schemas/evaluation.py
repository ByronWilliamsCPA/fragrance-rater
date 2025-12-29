"""Pydantic schemas for evaluation-related API models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EvaluationCreate(BaseModel):
    """Schema for creating a new evaluation."""

    fragrance_id: str = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)
    rating: int = Field(..., ge=1, le=5)
    notes: str | None = Field(None, max_length=2000)
    longevity_rating: int | None = Field(None, ge=1, le=5)
    sillage_rating: int | None = Field(None, ge=1, le=5)


class EvaluationUpdate(BaseModel):
    """Schema for updating an evaluation."""

    rating: int | None = Field(None, ge=1, le=5)
    notes: str | None = Field(None, max_length=2000)
    longevity_rating: int | None = Field(None, ge=1, le=5)
    sillage_rating: int | None = Field(None, ge=1, le=5)


class EvaluationResponse(BaseModel):
    """Schema for evaluation response."""

    id: str
    fragrance_id: str
    reviewer_id: str
    rating: int
    notes: str | None
    longevity_rating: int | None
    sillage_rating: int | None
    evaluated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
