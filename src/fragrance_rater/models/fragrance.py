"""Fragrance and note models.

This module defines the core fragrance data models including:
- Fragrance: Main fragrance entity with classification
- Note: Individual scent components
- NoteAlias: Spellings of a note that resolve to one canonical ``Note`` (R6)
- FragranceNote: Junction table with note position (top/heart/base)
- AccordType: Controlled lookup of accord codes (R6)
- FragranceAccord: Accord types with intensity weights and their provenance
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fragrance_rater.core.database import Base
from fragrance_rater.utils.labels import NOTE_KEY_MAX_LENGTH, normalize_note_key

if TYPE_CHECKING:
    from sqlalchemy.engine.default import DefaultExecutionContext
    from sqlalchemy.sql.schema import SchemaItem

    from fragrance_rater.models.calibration import VersionPerfumer
    from fragrance_rater.models.evaluation import Evaluation

NOTE_POSITIONS = ("top", "heart", "base", "flat")
"""Controlled values of ``FragranceNote.position`` (X-12); ``flat`` is a source that
lists notes without a pyramid."""

POSITION_VALUED_CATEGORIES = frozenset({"top", "heart", "middle", "base", "flat"})
"""Pyramid positions that older importers wrote into ``Note.category`` (X-02)."""

ACCORD_INTENSITY_SOURCES = ("measured", "positional", "absent")
"""Controlled values of ``FragranceAccord.intensity_source`` (X-04).

``measured`` is a weight a source reported. ``positional`` is a value derived from the
accord's place in a list (the Kaggle importer's ``1.0 - 0.15 * i``), so it carries
order and not strength. ``absent`` is an accord a source listed with no weight at all;
its ``intensity`` is a placeholder.
"""


def _sql_in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _name_key_from_name(context: DefaultExecutionContext) -> str:
    """Derive ``notes.name_key`` from the row's own ``name`` at insert time."""
    name: object = context.get_current_parameters()["name"]  # pyright: ignore[reportAny]
    return normalize_note_key(str(name))


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
        line (Mapped[str | None]): Collection or line within the brand, as the
            house names it. Not part of version identity.
        concentration (Mapped[str]): EDT, EDP, Parfum, etc.
        version_key (Mapped[str]): Stable formulation/version identifier.
        launch_year (Mapped[int | None]): Year of release.
        gender_target (Mapped[str]): Masculine, Feminine, or Unisex.
        primary_family (Mapped[str]): Michael Edwards Wheel family (Fresh, Floral,
            Amber, Woody).
        subfamily (Mapped[str]): More specific classification.
        intensity (Mapped[str | None]): Fresh, Crisp, Classical, or Rich.
        market_status (Mapped[str | None]): Whether the house still sells it
            (``core.vocabulary.MARKET_STATUSES``); NULL means unknown. This is
            the house's commercial status, not whether the household can get
            a sample (D4's candidate availability).
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
            fragrance. Never deleted through the fragrance: hard-deleting a
            rated fragrance fails on the RESTRICT foreign key.
        perfumers (Mapped[list[VersionPerfumer]]): Sourced perfumer
            attributions for this exact version.
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
        CheckConstraint(
            (
                "market_status IS NULL OR market_status IN ('in_production', "
                "'limited_edition', 'upcoming', 'discontinued')"
            ),
            name="market_status",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    brand: Mapped[str] = mapped_column(String(255), index=True)
    line: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    market_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

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
    # D-09: encounter history is never deleted through a fragrance. No
    # delete cascade, and passive_deletes="all" so the ORM does not load and
    # orphan these rows before issuing the DELETE; the database's RESTRICT
    # FK then rejects hard-deleting a fragrance that has evaluations (same
    # mechanism as Reviewer.worn_by_evaluations, ADR-011). Soft delete is
    # the only API path.
    evaluations: Mapped[list[Evaluation]] = relationship(
        back_populates="fragrance", passive_deletes="all"
    )
    # Perfumer attribution lives in calibration_version_perfumers, which carries
    # its own source_url per ADR-006's requirement that every claim keep its
    # provenance. The tables have existed since c731b42e9a01 but nothing could
    # reach them from Fragrance, so the attribution was write-only: populated by
    # the Parfumo scraper and readable by nothing.
    #
    # viewonly: the association row is provenance evidence, not a join table the
    # ORM may invent or delete rows in. Attribution is written deliberately by an
    # ingestion path that supplies source_url, never as a side effect of editing
    # a fragrance.
    perfumers: Mapped[list["VersionPerfumer"]] = relationship(
        "VersionPerfumer",
        primaryjoin="Fragrance.id == VersionPerfumer.fragrance_id",
        viewonly=True,
    )


class Note(Base):
    """Individual scent component.

    Identity is ``name_key``, the normalized form of ``name`` (see
    ``utils/labels.py``), so ``Oak Moss`` and ``oakmoss`` are one row. Other spellings
    and decided synonyms are ``NoteAlias`` rows pointing here; callers go through
    ``services/vocabulary.VocabularyResolver`` rather than querying ``name``.

    Attributes:
        id (Mapped[str]): Unique identifier (UUID).
        name (Mapped[str]): The first spelling recorded, kept verbatim (unique).
        name_key (Mapped[str]): Normalized identity key (unique).
        category (Mapped[str | None]): Olfactory family label (Citrus, Floral, Wood,
            etc.), or NULL when unknown. It never holds a pyramid position; that is
            ``FragranceNote.position`` (X-02).
        subcategory (Mapped[str | None]): More specific classification.
        aliases (Mapped[list[NoteAlias]]): Spellings that resolve to this note.
    """

    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name_key: Mapped[str] = mapped_column(
        String(NOTE_KEY_MAX_LENGTH), unique=True, default=_name_key_from_name
    )
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(50), nullable=True)

    aliases: Mapped[list[NoteAlias]] = relationship(back_populates="canonical_note")


class NoteAlias(Base):
    """One spelling of a note, resolved to a canonical ``Note`` under a mapping version.

    ``raw_label`` is verbatim and never normalized; ``alias_key`` is its normalized
    form. A ``curated`` row is a decision a person made (``vanille`` means
    ``vanilla``); an ``observed`` row only records a spelling an importer met that
    already normalizes to the note, so the raw label survives. The mapping version
    names the decision set: a changed decision is a new version, not an edit.

    A spelling is unique per version, and a key has at most one curated decision per
    version, so resolving a key never has two answers. Many observed spellings may
    share a key (``oakmoss`` and ``OAKMOSS``).

    Attributes:
        id (Mapped[str]): Unique identifier (UUID).
        raw_label (Mapped[str]): The spelling as given.
        alias_key (Mapped[str]): ``normalize_note_key(raw_label)``.
        canonical_note_id (Mapped[str]): The note this spelling resolves to.
        mapping_version (Mapped[str]): Decision set the row belongs to.
        origin (Mapped[str]): ``curated`` or ``observed``.
        created_at (Mapped[datetime]): When the row was recorded.
        canonical_note (Mapped[Note]): The note the spelling resolves to.
    """

    __tablename__ = "note_aliases"
    __table_args__: tuple[SchemaItem, ...] = (
        UniqueConstraint("raw_label", "mapping_version"),
        Index(
            "uq_note_aliases_curated_key",
            "alias_key",
            "mapping_version",
            unique=True,
            postgresql_where=text("origin = 'curated'"),
            sqlite_where=text("origin = 'curated'"),
        ),
        CheckConstraint("origin IN ('curated', 'observed')", name="origin"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    raw_label: Mapped[str] = mapped_column(String(NOTE_KEY_MAX_LENGTH))
    alias_key: Mapped[str] = mapped_column(String(NOTE_KEY_MAX_LENGTH))
    canonical_note_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notes.id", ondelete="RESTRICT"), index=True
    )
    mapping_version: Mapped[str] = mapped_column(String(50))
    origin: Mapped[str] = mapped_column(
        String(10), default="curated", server_default="curated"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )

    canonical_note: Mapped[Note] = relationship(back_populates="aliases")


class FragranceNote(Base):
    """Junction table linking fragrances to notes with position.

    Attributes:
        id (Mapped[str]): Surrogate primary key (UUID).
        fragrance_id (Mapped[str]): Foreign key to fragrance.
        note_id (Mapped[str]): Foreign key to note.
        position (Mapped[str]): Note position (top, heart, base, flat).
        rank (Mapped[int | None]): Zero-based place within the position as the source
            listed it, or NULL when the order was not recorded (X-12).
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
        CheckConstraint(f"position IN ({_sql_in(NOTE_POSITIONS)})", name="position"),
        CheckConstraint("rank IS NULL OR rank >= 0", name="rank"),
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
    position: Mapped[str] = mapped_column(String(10))  # top, heart, base, flat
    rank: Mapped[int | None] = mapped_column(nullable=True)

    fragrance: Mapped[Fragrance] = relationship(back_populates="notes")
    note: Mapped[Note] = relationship()


class AccordType(Base):
    """Controlled lookup of accord codes (X-03).

    ``FragranceAccord.accord_type`` is a foreign key here, so an accord has exactly one
    spelling: the lowercased, whitespace-collapsed ``code``. ``label`` keeps the first
    spelling a source used, for display.

    Attributes:
        code (Mapped[str]): Normalized accord code (primary key).
        label (Mapped[str]): First recorded spelling, verbatim.
        created_at (Mapped[datetime]): When the code was registered.
    """

    __tablename__ = "accord_types"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    label: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )


class FragranceAccord(Base):
    """Accord type with intensity for a fragrance.

    Attributes:
        fragrance_id (Mapped[str]): Foreign key to fragrance.
        accord_type (Mapped[str]): ``AccordType.code`` (e.g., citrus, woody, sweet).
        intensity (Mapped[float]): Intensity weight from 0.0 to 1.0. Read it with
            ``intensity_source``: a ``positional`` value is a list place, not a
            strength (X-04).
        intensity_source (Mapped[str]): ``measured``, ``positional``, or ``absent``.
        rank (Mapped[int | None]): Zero-based place in the source's accord list, or
            NULL when the order was not recorded. Kept so list order survives as a
            rank feature when the positional intensity is excluded.
        fragrance (Mapped[Fragrance]): Owning fragrance.
    """

    __tablename__ = "fragrance_accords"
    __table_args__: tuple[SchemaItem, ...] = (
        CheckConstraint(
            f"intensity_source IN ({_sql_in(ACCORD_INTENSITY_SOURCES)})",
            name="intensity_source",
        ),
        CheckConstraint("rank IS NULL OR rank >= 0", name="rank"),
    )

    fragrance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    accord_type: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("accord_types.code", ondelete="RESTRICT"),
        primary_key=True,
    )
    intensity: Mapped[float] = mapped_column(Float)
    intensity_source: Mapped[str] = mapped_column(
        String(10), default="measured", server_default="measured"
    )
    rank: Mapped[int | None] = mapped_column(nullable=True)

    fragrance: Mapped[Fragrance] = relationship(back_populates="accords")


class FragranceGtin(Base):
    """A barcode (GTIN) identifying one retail SKU of a fragrance version.

    A GTIN is assigned per exact SKU by the manufacturer, so it is the
    strongest identity link this project has (see ``utils/gtin.py``). One
    version can have several (one per bottle size); one GTIN names exactly
    one version, hence the primary key. Every row cites the evidence that
    established it (ADR-006): a barcode with no source is not recorded.

    Attributes:
        gtin (Mapped[str]): GS1 check-digit-valid GTIN, normalized to 14
            digits (``utils.gtin.normalize_gtin``).
        fragrance_id (Mapped[str]): The version the SKU belongs to.
        source_snapshot_id (Mapped[str]): Evidence row asserting the link.
        created_at (Mapped[datetime]): When the link was recorded.
    """

    __tablename__ = "fragrance_gtins"
    __table_args__ = (CheckConstraint("length(gtin) = 14", name="length"),)

    gtin: Mapped[str] = mapped_column(String(14), primary_key=True)
    fragrance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fragrances.id", ondelete="RESTRICT"), index=True
    )
    source_snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("calibration_source_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
