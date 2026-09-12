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
    """Append-only submitted response; post-reveal never replaces blind data."""

    __tablename__ = "calibration_observations"
    __table_args__ = (
        CheckConstraint("liking IS NULL OR (liking >= 0 AND liking <= 10)"),
        CheckConstraint("intensity IS NULL OR (intensity >= 0 AND intensity <= 5)"),
        CheckConstraint(
            "detected IS NULL OR detected OR (intensity = 0 AND intensity IS NOT NULL AND liking IS NULL)"
        ),
        CheckConstraint("elapsed_minutes >= 0"),
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
    responses: Mapped[dict[str, object]] = mapped_column(JSON)
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


class FragellaLookup(Base):
    """A Fragella reference-lookup attempt for a fragrance.

    # #ASSUME: data-integrity: distinct from SourceSnapshot - this is not
    # adopted source evidence (see ADR-002's 2026-09-13 amendment).
    # `results` is read-only reference data a manager can compare against
    # while verifying identity; nothing here is ever written back into
    # `Fragrance` fields or copied into a membership's
    # `identity_evidence`/`verification_evidence` automatically. Recorded
    # so a manager can see which fragrances still have not been checked
    # ("fill holes") without re-spending one of the account's 20
    # monthly requests just to find out.
    # #VERIFY: no code path other than FragellaLookupService writes a
    # Fragrance column or Membership.selection from a FragellaLookup row.
    """

    __tablename__ = "fragella_lookups"
    # #ASSUME: data-integrity: `status` has exactly two legal values today
    # (FragellaLookupService.run_lookup only ever writes "error" or
    # "success"); a bare String(20) column upheld the invariant that
    # `status` moves in lockstep with `error_message`/`results` only by
    # programmer discipline in that one write path, so a future write path
    # could otherwise leave e.g. status="success" with a stale
    # error_message. A CHECK constraint moves that enforcement to the
    # schema, matching the existing IN(...) precedent on
    # PilotOperationalEvent.event_type.
    # #VERIFY: covered by a test asserting a third value fails at flush().
    __table_args__ = (CheckConstraint("status IN ('error', 'success')"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    fragrance_id: Mapped[str] = mapped_column(
        ForeignKey("fragrances.id", ondelete="RESTRICT"), index=True
    )
    queried_at: Mapped[datetime] = mapped_column(default=now_naive_utc)
    query: Mapped[str] = mapped_column(String(500))
    requested_by: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20))
    error_message: Mapped[str | None] = mapped_column(Text)
    results: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)


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
