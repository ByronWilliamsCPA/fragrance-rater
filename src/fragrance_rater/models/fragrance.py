"""Fragrance and note models.

This module defines the core fragrance data models including:
- Fragrance: Main fragrance entity with classification
- Note: Individual scent components
- FragranceNote: Junction table with note position (top/heart/base)
- FragranceAccord: Accord types with intensity weights
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Float, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fragrance_rater.core.database import Base

if TYPE_CHECKING:
    from fragrance_rater.models.evaluation import Evaluation


class Fragrance(Base):
    """Fragrance entity with classification data.

    Attributes:
        id (Mapped[str]): Unique identifier (UUID).
        name (Mapped[str]): Fragrance name.
        brand (Mapped[str]): Brand/house name.
        concentration (Mapped[str]): EDT, EDP, Parfum, etc.
        launch_year (Mapped[int | None]): Year of release.
        gender_target (Mapped[str]): Masculine, Feminine, or Unisex.
        primary_family (Mapped[str]): Michael Edwards Wheel family (Fresh, Floral,
            Amber, Woody).
        subfamily (Mapped[str]): More specific classification.
        intensity (Mapped[str | None]): Fresh, Crisp, Classical, or Rich.
        data_source (Mapped[str]): Origin of data (manual, kaggle, parfumo).
        external_id (Mapped[str | None]): ID from external data source.
        parfumo_url (Mapped[str | None]): Source page on Parfumo, when scraped.
        created_at (Mapped[datetime]): Creation timestamp.
        updated_at (Mapped[datetime]): Last update timestamp.
        deleted_at (Mapped[datetime | None]): Soft-delete timestamp; NULL
            means active. Set by DELETE routes instead of removing the row.
        notes (Mapped[list[FragranceNote]]): Note associations with pyramid
            position.
        accords (Mapped[list[FragranceAccord]]): Accord associations with
            intensity.
        evaluations (Mapped[list[Evaluation]]): Reviewer evaluations of this
            fragrance.
    """

    __tablename__ = "fragrances"
    # Major finding 8: no UNIQUE constraint on (name, brand) let the same
    # catalog entry be imported twice with no detection. `uq_fragrance_name_brand`
    # is the reference implementation preserved from prior review; the search
    # index name (`ix_fragrance_search`) is likewise the agreed naming.
    # #EDGE: data-integrity: this does not include `concentration`, so a
    # legitimate EDT/EDP pair sharing a name and brand will collide.
    # #VERIFY: if that turns out to happen in practice, widen the constraint
    # to include `concentration` in a follow-up migration.
    #
    # `uq_fragrance_name_brand` is a partial unique index scoped to
    # `deleted_at IS NULL` rather than a plain UniqueConstraint: see the
    # resolved RAD note on `deleted_at` below for why (soft-deleted rows
    # must not permanently block recreating the same (name, brand) pair).
    # `sqlite_where` mirrors `postgresql_where` so the SQLite test database
    # (built from this metadata via `Base.metadata.create_all`, not this
    # migration) enforces the same scoped uniqueness as production.
    __table_args__ = (
        Index(
            "uq_fragrance_name_brand",
            "name",
            "brand",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_fragrance_search", "name", "brand"),
    )

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
    parfumo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now(), onupdate=func.now()
    )

    # Critical finding 2: soft-delete. DELETE routes set this timestamp
    # instead of issuing a real DELETE, so a deleted fragrance never
    # triggers the cascade="all, delete-orphan" below on its evaluations
    # (no row is actually removed). Every read query against this table
    # must filter WHERE deleted_at IS NULL; see fragrance_service.py,
    # recommendation_service.py, api/recommendations.py, and
    # parfumo_scraper.py's dedup lookups.
    # Resolved: uq_fragrance_name_brand (Major finding 8) was originally a
    # plain UniqueConstraint, so soft-deleting a fragrance and later
    # re-creating or re-scraping the same (name, brand) still raised a
    # UNIQUE violation against the deleted row forever. It is now a partial
    # unique index scoped to `deleted_at IS NULL` (see __table_args__
    # above and migration 22eed1bf0509), so uniqueness is enforced among
    # live rows only.
    deleted_at: Mapped[datetime | None] = mapped_column(
        nullable=True, default=None, index=True
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
        id (Mapped[str]): Unique identifier (UUID).
        name (Mapped[str]): Note name (unique).
        category (Mapped[str]): Primary category (Citrus, Floral, Wood, etc.).
        subcategory (Mapped[str | None]): More specific classification.
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
        id (Mapped[str]): Surrogate primary key (UUID).
        fragrance_id (Mapped[str]): Foreign key to fragrance.
        note_id (Mapped[str]): Foreign key to note.
        position (Mapped[str]): Note position (top, heart, base).
        fragrance (Mapped[Fragrance]): Owning fragrance.
        note (Mapped[Note]): Referenced note.
    """

    __tablename__ = "fragrance_notes"
    # Critical finding 3: the old composite primary key was
    # (fragrance_id, note_id), which excluded `position` and so collided
    # whenever the same note legitimately appeared in two pyramid
    # positions for one fragrance (e.g. musk in both heart and base),
    # crashing the import. The ratified fix is a real surrogate `id`
    # primary key (matching the UUID-string style used by every other
    # table here), not simply widening the composite PK to include
    # `position`, plus this UNIQUE constraint so a genuine duplicate (the
    # same note in the same position twice) is still rejected.
    __table_args__ = (
        UniqueConstraint(
            "fragrance_id",
            "note_id",
            "position",
            name="uq_fragrance_note_position",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    fragrance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fragrances.id", ondelete="CASCADE"), index=True
    )
    note_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notes.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[str] = mapped_column(String(10))  # top, heart, base

    fragrance: Mapped[Fragrance] = relationship(back_populates="notes")
    note: Mapped[Note] = relationship()


class FragranceAccord(Base):
    """Accord type with intensity for a fragrance.

    Attributes:
        fragrance_id (Mapped[str]): Foreign key to fragrance.
        accord_type (Mapped[str]): Type of accord (e.g., citrus, woody, sweet).
        intensity (Mapped[float]): Intensity weight from 0.0 to 1.0.
        fragrance (Mapped[Fragrance]): Owning fragrance.
    """

    __tablename__ = "fragrance_accords"

    fragrance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    accord_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    intensity: Mapped[float] = mapped_column(Float)

    fragrance: Mapped[Fragrance] = relationship(back_populates="accords")
