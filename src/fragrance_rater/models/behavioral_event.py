"""General behavioral outcomes, independent of any recommendation (R7a, X-23).

``RecommendationResponseRevision`` answers "what happened to this specific
recommendation". ``BehavioralEvent`` answers "what did this reviewer do with
this exact fragrance version", whether or not anything recommended it, so
intent labels can be checked against behavior and ownership can be
reconstructed as of any date (capture assessment sections 8 and 13.10).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.schema import SchemaItem

from fragrance_rater.core.database import Base
from fragrance_rater.models.calibration import identifier, in_check
from fragrance_rater.utils.timestamps import now_naive_utc

# data-model-gap-analysis section 5 ("Behavioral event types") plus ``returned``
# and ``declined`` from the capture assessment section 8. Migration
# 3f14014a49cb writes the same list literally.
BEHAVIORAL_EVENT_TYPES: tuple[str, ...] = (
    "sampled",
    "wore",
    "rewore",
    "wishlisted",
    "removed_from_wishlist",
    "bought_sample",
    "bought_decant",
    "bought_travel",
    "bought_bottle",
    "finished_sample",
    "finished_bottle",
    "repurchased",
    "returned",
    "gifted",
    "sold",
    "gave_away",
    "declined",
)
# Capture assessment section 8: "declined because of price, availability,
# performance, redundancy, or another stated reason".
DECLINE_REASONS: tuple[str, ...] = (
    "price",
    "availability",
    "performance",
    "redundancy",
    "other",
)


class BehavioralEvent(Base):
    """One append-only behavioral event for a reviewer and fragrance version.

    A purchase is not proof of liking and no purchase is not proof of dislike;
    the reason and offer conditions are kept so later analysis can tell.

    Columns:
        reviewer_id: Whose behavior this is.
        fragrance_id: The exact catalog version (ADR-006).
        event_type: What happened, from ``BEHAVIORAL_EVENT_TYPES``.
        occurred_on: Reviewer-local date of the event. Required, because a
            retrospective report usually knows the day but not the time.
        occurred_at: Exact time when known, naive UTC.
        evaluator_timezone: IANA zone for reading ``occurred_at`` locally.
        size_ml: Nominal size involved (a bought decant, a finished bottle).
        price_amount: Price paid or offered, in ``currency``.
        currency: ISO 4217 code; required whenever ``price_amount`` is set.
        decline_reason: Only on ``declined`` events.
        details: Free-text detail as reported.
        source_observation_id: Calibration observation this follows, if any.
        source_impression_id: Recommendation impression this follows, if any.
        recorded_by: Who was at the keyboard.
        created_at: Server receipt time.
    """

    __tablename__ = "behavioral_events"
    # #ASSUME: data-integrity: ADR-011 scoping. This table is outcome evidence
    # only; no affinity or recommendation scorer reads it. A `wore` event
    # records the reviewer's own wear. "On others" opinions stay on
    # `evaluations.worn_by_reviewer_id`.
    # #VERIFY: no scoring module imports BehavioralEvent (R7a service PR test).
    __table_args__: tuple[SchemaItem, ...] = (
        CheckConstraint(
            in_check("event_type", BEHAVIORAL_EVENT_TYPES, nullable=False),
            name="event_type_valid",
        ),
        CheckConstraint(
            in_check("decline_reason", DECLINE_REASONS),
            name="decline_reason_valid",
        ),
        CheckConstraint(
            "decline_reason IS NULL OR event_type = 'declined'",
            name="decline_reason_requires_declined",
        ),
        CheckConstraint("size_ml IS NULL OR size_ml > 0", name="size_ml_positive"),
        CheckConstraint(
            "price_amount IS NULL OR price_amount >= 0",
            name="price_amount_nonnegative",
        ),
        CheckConstraint(
            "price_amount IS NULL OR currency IS NOT NULL",
            name="price_requires_currency",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.id", ondelete="RESTRICT"), index=True
    )
    fragrance_id: Mapped[str] = mapped_column(
        ForeignKey("fragrances.id", ondelete="RESTRICT"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(30))
    occurred_on: Mapped[date] = mapped_column(Date)
    occurred_at: Mapped[datetime | None] = mapped_column(nullable=True)
    evaluator_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    # #ASSUME: payment/financial: a reported price is a household record, not
    # a transaction; Numeric keeps it exact (CLAUDE.md: Decimal precision).
    # #VERIFY: the service accepts Decimal, never float, for this field.
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_observation_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_observations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    source_impression_id: Mapped[str | None] = mapped_column(
        ForeignKey("recommendation_impressions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    recorded_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc, index=True)
