"""Pydantic schemas for reviewer-related API models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from datetime import datetime


class ReviewerCreate(BaseModel):
    """Schema for creating a new reviewer."""

    name: str = Field(..., min_length=1, max_length=100)


class ReviewerResponse(BaseModel):
    """Schema for reviewer response."""

    id: str
    name: str
    created_at: datetime
    evaluation_count: int = 0

    model_config = {"from_attributes": True}
