"""Controlled measurement records sharing the existing version catalog."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from fragrance_rater.core.database import Base
from fragrance_rater.utils.timestamps import now_naive_utc


def identifier() -> str:
    """Return an opaque identifier."""
    return str(uuid4())


class Program(Base):
    """Immutable protocol definition once activated."""

    __tablename__ = "calibration_programs"
    __table_args__ = (UniqueConstraint("name", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)
    locked_at: Mapped[datetime | None]


class Membership(Base):
    """Version-resolved stimulus with concealed experimental role."""

    __tablename__ = "calibration_memberships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_programs.id", ondelete="RESTRICT"), index=True
    )
    fragrance_id: Mapped[str] = mapped_column(
        ForeignKey("fragrances.id", ondelete="RESTRICT"), index=True
    )
    role: Mapped[str] = mapped_column(String(30))
    repeat_of_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_memberships.id", ondelete="RESTRICT")
    )
    group_name: Mapped[str] = mapped_column(String(200), default="Baseline")
    selection: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class Enrollment(Base):
    """Per-evaluator reveal gate and explicit recorder grants."""

    __tablename__ = "calibration_enrollments"
    __table_args__ = (UniqueConstraint("program_id", "reviewer_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_programs.id", ondelete="RESTRICT")
    )
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.id", ondelete="RESTRICT"), index=True
    )
    recorder_usernames: Mapped[list[str]] = mapped_column(JSON)
    skin_plan_locked_at: Mapped[datetime | None]
    revealed_at: Mapped[datetime | None]
    revealed_by: Mapped[str | None] = mapped_column(String(255))


class CalibrationSession(Base):
    """Ordered session; capacity is protocol data rather than a constant."""

    __tablename__ = "calibration_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    enrollment_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_enrollments.id", ondelete="RESTRICT"), index=True
    )
    context: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)


class Presentation(Base):
    """A concealed presentation; repeats have independent random codes."""

    __tablename__ = "calibration_presentations"
    __table_args__ = (
        UniqueConstraint("session_id", "position"),
        UniqueConstraint("blind_code"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_sessions.id", ondelete="RESTRICT"), index=True
    )
    membership_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_memberships.id", ondelete="RESTRICT")
    )
    blind_code: Mapped[str] = mapped_column(String(24))
    position: Mapped[int] = mapped_column(Integer)
    skin_reason: Mapped[str | None] = mapped_column(Text)
    blotter_locked_at: Mapped[datetime | None]
    skin_locked_at: Mapped[datetime | None]


class Observation(Base):
    """Append-only submitted response; post-reveal never replaces blind data.

    Every field below (other than the identity/timing columns) mirrors a
    field of ``schemas.calibration.ResponseInput`` one-for-one by name, so
    ``calibration_service.observe()`` can populate them by splatting
    ``data.model_dump()`` rather than maintaining a second, drift-prone list.
    These used to be flattened into one untyped ``responses`` JSON column;
    that buried validated, ML-relevant values (``would_wear``, sensory
    dimensions, ``perceived_notes``, ...) where they could not be indexed,
    constrained, or queried, and where the frozen training manifest in
    ``preference_history.py`` could only forward them onward as an opaque
    blob. They are now first-class, individually bounded columns so this
    data is directly usable as ML features/labels without a parsing step.
    ``perceived_notes`` stays a JSON array of free-text labels rather than a
    join against ``Note`` (full normalization is a separate, larger change);
    ``likes``/``dislikes``/``reminds_me_of``/``comments`` stay raw text,
    preserved unchanged even if a future LLM extraction pipeline derives
    structured values from them elsewhere.
    """

    __tablename__ = "calibration_observations"
    __table_args__ = (
        CheckConstraint("liking IS NULL OR (liking >= 0 AND liking <= 10)"),
        CheckConstraint("intensity IS NULL OR (intensity >= 0 AND intensity <= 5)"),
        CheckConstraint(
            "detected IS NULL OR detected OR (intensity = 0 AND intensity IS NOT NULL AND liking IS NULL)"
        ),
        CheckConstraint("elapsed_minutes >= 0"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 5)"),
        CheckConstraint("sweetness IS NULL OR (sweetness >= 0 AND sweetness <= 5)"),
        CheckConstraint("freshness IS NULL OR (freshness >= 0 AND freshness <= 5)"),
        CheckConstraint("density IS NULL OR (density >= 0 AND density <= 5)"),
        CheckConstraint(
            "familiarity IS NULL OR (familiarity >= 0 AND familiarity <= 5)"
        ),
        CheckConstraint("dryness IS NULL OR (dryness >= 0 AND dryness <= 5)"),
        CheckConstraint(
            "clean_soapy IS NULL OR (clean_soapy >= 0 AND clean_soapy <= 5)"
        ),
        CheckConstraint(
            "earthy_rooty IS NULL OR (earthy_rooty >= 0 AND earthy_rooty <= 5)"
        ),
        CheckConstraint(
            "bodily_animalic IS NULL OR (bodily_animalic >= 0 AND bodily_animalic <= 5)"
        ),
        CheckConstraint("discomfort IS NULL OR (discomfort >= 0 AND discomfort <= 5)"),
        CheckConstraint(
            "opening_liking IS NULL OR (opening_liking >= 0 AND opening_liking <= 10)"
        ),
        CheckConstraint(
            "drydown_liking IS NULL OR (drydown_liking >= 0 AND drydown_liking <= 10)"
        ),
        CheckConstraint("would_wear IS NULL OR (would_wear >= 0 AND would_wear <= 10)"),
        CheckConstraint("would_buy IS NULL OR (would_buy >= 0 AND would_buy <= 10)"),
        CheckConstraint(
            "artistic_appreciation IS NULL OR "
            "(artistic_appreciation >= 0 AND artistic_appreciation <= 10)"
        ),
        CheckConstraint("projection IS NULL OR (projection >= 0 AND projection <= 5)"),
        CheckConstraint("longevity_minutes IS NULL OR longevity_minutes >= 0"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    presentation_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_presentations.id", ondelete="RESTRICT"), index=True
    )
    stage: Mapped[str] = mapped_column(String(20))
    phase: Mapped[str] = mapped_column(String(20))
    elapsed_minutes: Mapped[int] = mapped_column(Integer, default=0)
    detected: Mapped[bool | None] = mapped_column(Boolean)
    intensity: Mapped[int | None] = mapped_column(Integer)
    liking: Mapped[int | None] = mapped_column(Integer)

    # Structured evaluator perception (published-vs-perceived stays distinct:
    # these are always what the evaluator reported, never a catalog fact).
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sweetness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    freshness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    density: Mapped[int | None] = mapped_column(Integer, nullable=True)
    familiarity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dryness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clean_soapy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    earthy_rooty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bodily_animalic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discomfort: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Temporal liking and performance.
    opening_liking: Mapped[int | None] = mapped_column(Integer, nullable=True)
    drydown_liking: Mapped[int | None] = mapped_column(Integer, nullable=True)
    would_wear: Mapped[int | None] = mapped_column(Integer, nullable=True)
    would_buy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artistic_appreciation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    projection: Mapped[int | None] = mapped_column(Integer, nullable=True)
    longevity_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Perceived notes and raw free text (see class docstring).
    perceived_notes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    likes: Mapped[str | None] = mapped_column(Text, nullable=True)
    dislikes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminds_me_of: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    recorded_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)


class ModelCheckpoint(Base):
    """Frozen data manifest and typed predictions, never recomputed in place."""

    __tablename__ = "calibration_checkpoints"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    enrollment_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_enrollments.id", ondelete="RESTRICT")
    )
    algorithm_version: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)
    manifest: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    predictions: Mapped[list[dict[str, object]]] = mapped_column(JSON)


class SourceSnapshot(Base):
    """Refreshable source evidence stored independently of human observations."""

    __tablename__ = "calibration_source_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    fragrance_id: Mapped[str] = mapped_column(
        ForeignKey("fragrances.id", ondelete="RESTRICT")
    )
    source_url: Mapped[str] = mapped_column(String(1000))
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified")
    retrieved_at: Mapped[datetime] = mapped_column(default=now_naive_utc)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)


class Perfumer(Base):
    """Named source contributor."""

    __tablename__ = "calibration_perfumers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class VersionPerfumer(Base):
    """Many-to-many version attribution with source provenance."""

    __tablename__ = "calibration_version_perfumers"
    fragrance_id: Mapped[str] = mapped_column(
        ForeignKey("fragrances.id", ondelete="RESTRICT"), primary_key=True
    )
    perfumer_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_perfumers.id", ondelete="RESTRICT"), primary_key=True
    )
    source_url: Mapped[str] = mapped_column(String(1000))
