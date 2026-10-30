"""Append-only consent events (capture assessment 13.11 and 18.5).

Consent is recorded per evaluator and per scope, as a sequence of ``granted``
and ``withdrawn`` events. A reviewer's current state for a scope is their
latest event for it; nothing is updated or deleted, so the state at any past
moment (when a session context was written, when a dataset was exported) can
be reconstructed.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.schema import SchemaItem

from fragrance_rater.core.database import Base
from fragrance_rater.models.calibration import identifier, in_check
from fragrance_rater.utils.timestamps import now_naive_utc

# Migration cd1e2375a2e4 writes the same lists literally (R2: migrations do not
# import models). A unit test pins each tuple to its CHECK.
CONSENT_EVENT_TYPES: tuple[str, ...] = ("granted", "withdrawn")
# What a consent covers. ``session_context`` is 13.11's sensitive optional
# session-context answers (illness, allergy, hormonal context). The other four
# are 18.5's contribution state, which applies to ordinary observations too:
# research use within the household, inclusion in aggregate reporting, future
# model-training contribution, and inclusion in an export leaving the household.
CONSENT_SCOPES: tuple[str, ...] = (
    "session_context",
    "household_research",
    "aggregate_reporting",
    "model_training",
    "research_export",
)


class ConsentEvent(Base):
    """One grant or withdrawal of one consent scope by one evaluator.

    A consent screen that covers several scopes writes one row per scope,
    sharing ``consent_text_version`` and ``consent_text_sha256``. A grant
    names the text the evaluator saw; a withdrawal need not (it withdraws
    whatever was granted).

    Columns:
        reviewer_id: The evaluator whose consent this is.
        enrollment_id: The enrollment whose consent screen recorded it, when
            it was recorded inside a controlled program.
        event_type: ``granted`` or ``withdrawn``.
        scope: What the event covers (``CONSENT_SCOPES``).
        consent_text_version: Version label of the consent text shown;
            required on a grant.
        consent_text_sha256: Hex SHA-256 of the exact text shown, so a
            version label reused for changed wording is detectable.
        occurred_at: When the evaluator granted or withdrew (client clock,
            naive UTC). This is the consent timestamp.
        recorded_by: Who was at the keyboard (may differ from the evaluator).
        note: Free text, e.g. how a verbal withdrawal was received.
        created_at: Server receipt time.
    """

    __tablename__ = "consent_events"
    # #CRITICAL: security: this table is the precondition for collecting the
    # sensitive session context (SessionContext's #CRITICAL tag). It is
    # append-only: a withdrawal is a new row, never a delete or update of the
    # grant, so the consent in force when any context row was written stays
    # provable.
    # #VERIFY: the R7b write path reads the latest event per (reviewer, scope)
    # ordered by occurred_at then created_at, and refuses context writes
    # unless it is a ``session_context`` grant.
    __table_args__: tuple[SchemaItem, ...] = (
        CheckConstraint(
            in_check("event_type", CONSENT_EVENT_TYPES, nullable=False),
            name="event_type_valid",
        ),
        CheckConstraint(
            in_check("scope", CONSENT_SCOPES, nullable=False), name="scope_valid"
        ),
        CheckConstraint(
            "event_type <> 'granted' OR (consent_text_version IS NOT NULL AND TRIM(consent_text_version) <> '')",
            name="grant_requires_text_version",
        ),
        CheckConstraint(
            "consent_text_sha256 IS NULL OR length(consent_text_sha256) = 64",
            name="consent_text_sha256_length",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.id", ondelete="RESTRICT"), index=True
    )
    enrollment_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_enrollments.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(20))
    scope: Mapped[str] = mapped_column(String(30))
    consent_text_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    consent_text_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc)
