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


class TrainingEligibility(Base):
    """Lookup table for whether a fragrance's evaluations may train affinities.

    ADR-014: the stable-code/display-label/sort_order/active lookup pattern
    ADR-010 already proposed but never built. No existing table already
    implements that exact shape: `FragellaLookup`/`fragella_lookups` is a
    reference-lookup attempt log (id, fragrance_id, status, results), not a
    seeded code/display_label/sort_order/active lookup, so this table is the
    first concrete instance of the pattern ADR-010 described, not a repeat
    of an existing one. Seeded by migration data insert only (`eligible`,
    `excluded_pending_classification`, `excluded_manual`); no management API
    is added for this table in this pass, matching `fragella_lookups`' own
    lack of a dedicated CRUD API (though that table is written by
    `FragellaLookupService`, not migration seed data, for an unrelated
    reason: it holds a growing operational log, not a fixed vocabulary).

    Attributes:
        code (Mapped[str]): Stable machine-readable code; primary key.
        display_label (Mapped[str]): Human-readable label for display.
        sort_order (Mapped[int]): Display ordering among active rows.
        active (Mapped[bool]): Whether this code may still be assigned.
    """

    __tablename__ = "training_eligibilities"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    display_label: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column()
    active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))


class Fragrance(Base):
    """Fragrance entity with classification data.

    Attributes:
        id (Mapped[str]): Unique identifier (UUID).
        name (Mapped[str]): Fragrance name.
        brand (Mapped[str]): Brand/house name.
        concentration (Mapped[str]): EDT, EDP, Parfum, etc.
        version_key (Mapped[str]): Stable formulation/version identifier.
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
        training_eligibility_code (Mapped[str | None]): FK to
            ``training_eligibilities.code``. NULL (every row as of ADR-014)
            means "eligible"; see ADR-014 and `core/vocabulary.py`'s
            `TRAINING_INELIGIBLE_CODES` for the codes that exclude a
            fragrance from affinity scoring.
        notes (Mapped[list[FragranceNote]]): Note associations with pyramid
            position.
        accords (Mapped[list[FragranceAccord]]): Accord associations with
            intensity.
        evaluations (Mapped[list[Evaluation]]): Reviewer evaluations of this
            fragrance.
    """

    __tablename__ = "fragrances"
    # Preserve distinct concentrations and formulation/version identities.
    # Live rows are unique; archived rows do not block replacement records.
    __table_args__ = (
        Index(
            "uq_fragrance_version",
            "name",
            "brand",
            "concentration",
            "version_key",
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
    version_key: Mapped[str] = mapped_column(
        String(200), default="legacy", server_default="legacy"
    )
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

    # ADR-014: nullable, no default, no backfill. NULL means "eligible" for
    # every existing row; only a future write path that explicitly assigns
    # an excluded code opts a fragrance out of RecommendationService's
    # affinity accumulation. No relationship object is declared here (the
    # service layer only needs the code string, not the full
    # TrainingEligibility row), keeping this addition minimal.
    # #ASSUME: data-integrity: "NULL means eligible" is defined only here
    # and in ADR-014, not enforced by any CHECK/default at the schema
    # level; a future migration that adds a real default (e.g. explicitly
    # writing "eligible") would need to keep this NULL-means-eligible
    # reading consistent, or update every reader (RecommendationService,
    # this column's own comment, ADR-014) in the same change.
    # #VERIFY: any new code path reading this column treats NULL the same
    # as an explicit "eligible" row rather than as a third, unhandled
    # state; see RecommendationService.build_preference_profile's check
    # against TRAINING_INELIGIBLE_CODES (NULL is never a member of that
    # frozenset, so it always falls through to "eligible" by construction).
    training_eligibility_code: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("training_eligibilities.code", ondelete="RESTRICT"),
        nullable=True,
        index=True,
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
