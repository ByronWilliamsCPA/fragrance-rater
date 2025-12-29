"""Fragrance and note models.

This module defines the core fragrance data models including:
- Fragrance: Main fragrance entity with classification
- Note: Individual scent components
- FragranceNote: Junction table with note position (top/heart/base)
- FragranceAccord: Accord types with intensity weights
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fragrance_rater.core.database import Base

if TYPE_CHECKING:
    from datetime import datetime

    from fragrance_rater.models.evaluation import Evaluation


class Fragrance(Base):
    """Fragrance entity with classification data.

    Attributes:
        id: Unique identifier (UUID).
        name: Fragrance name.
        brand: Brand/house name.
        concentration: EDT, EDP, Parfum, etc.
        launch_year: Year of release.
        gender_target: Masculine, Feminine, or Unisex.
        primary_family: Michael Edwards Wheel family (Fresh, Floral, Amber, Woody).
        subfamily: More specific classification.
        intensity: Fresh, Crisp, Classical, or Rich.
        data_source: Origin of data (manual, kaggle, fragella).
        external_id: ID from external data source.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "fragrances"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    brand: Mapped[str] = mapped_column(String(255), index=True)
    concentration: Mapped[str] = mapped_column(String(50))
    launch_year: Mapped[int | None] = mapped_column(nullable=True)
    gender_target: Mapped[str] = mapped_column(String(20))

    # Classification (Michael Edwards Wheel)
    primary_family: Mapped[str] = mapped_column(String(50))
    subfamily: Mapped[str] = mapped_column(String(50))
    intensity: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Data provenance
    data_source: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    notes: Mapped[list[FragranceNote]] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan"
    )
    accords: Mapped[list[FragranceAccord]] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan"
    )
    evaluations: Mapped[list[Evaluation]] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan"
    )


class Note(Base):
    """Individual scent component.

    Attributes:
        id: Unique identifier (UUID).
        name: Note name (unique).
        category: Primary category (Citrus, Floral, Wood, etc.).
        subcategory: More specific classification.
    """

    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(50))
    subcategory: Mapped[str | None] = mapped_column(String(50), nullable=True)


class FragranceNote(Base):
    """Junction table linking fragrances to notes with position.

    Attributes:
        fragrance_id: Foreign key to fragrance.
        note_id: Foreign key to note.
        position: Note position (top, heart, base).
    """

    __tablename__ = "fragrance_notes"

    fragrance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    note_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[str] = mapped_column(String(10))  # top, heart, base

    fragrance: Mapped[Fragrance] = relationship(back_populates="notes")
    note: Mapped[Note] = relationship()


class FragranceAccord(Base):
    """Accord type with intensity for a fragrance.

    Attributes:
        fragrance_id: Foreign key to fragrance.
        accord_type: Type of accord (e.g., citrus, woody, sweet).
        intensity: Intensity weight from 0.0 to 1.0.
    """

    __tablename__ = "fragrance_accords"

    fragrance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    accord_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    intensity: Mapped[float] = mapped_column(Float)

    fragrance: Mapped[Fragrance] = relationship(back_populates="accords")
