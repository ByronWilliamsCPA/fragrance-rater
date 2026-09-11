"""Auditable recommendation impressions, responses, and linked outcomes."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
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
    """Return a new opaque identifier."""
    return str(uuid4())


class RecommendationRun(Base):
    """One immutable generation event with frozen model inputs."""

    __tablename__ = "recommendation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.id", ondelete="RESTRICT"), index=True
    )
    algorithm_version: Mapped[str] = mapped_column(String(100))
    candidate_strategy: Mapped[str] = mapped_column(String(100))
    filters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    input_manifest: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    source_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc, index=True)
    recorded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class RecommendationImpression(Base):
    """A candidate persisted exactly once within a recommendation run."""

    __tablename__ = "recommendation_impressions"
    __table_args__ = (
        UniqueConstraint("run_id", "fragrance_id"),
        UniqueConstraint("run_id", "rank"),
        CheckConstraint("rank > 0"),
        CheckConstraint("score_value >= 0 AND score_value <= 1"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("recommendation_runs.id", ondelete="RESTRICT"), index=True
    )
    fragrance_id: Mapped[str] = mapped_column(
        ForeignKey("fragrances.id", ondelete="RESTRICT"), index=True
    )
    rank: Mapped[int] = mapped_column(Integer)
    score_type: Mapped[str] = mapped_column(String(50))
    score_value: Mapped[float] = mapped_column(Float)
    explanation_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    shown_at: Mapped[datetime] = mapped_column(default=now_naive_utc, index=True)


class RecommendationResponseRevision(Base):
    """Append-only revision of feedback for one persisted impression."""

    __tablename__ = "recommendation_response_revisions"
    __table_args__ = (
        UniqueConstraint("impression_id", "revision"),
        CheckConstraint("revision > 0"),
        CheckConstraint(
            "sampling_state IS NULL OR sampling_state IN "
            "('PLANNED', 'ACQUIRED', 'SAMPLED', 'UNAVAILABLE')"
        ),
        CheckConstraint(
            "NOT (outcome_evaluation_id IS NOT NULL "
            "AND outcome_observation_id IS NOT NULL)"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    impression_id: Mapped[str] = mapped_column(
        ForeignKey("recommendation_impressions.id", ondelete="RESTRICT"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    interested: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sampling_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unavailable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_evaluation_id: Mapped[str | None] = mapped_column(
        ForeignKey("evaluations.id", ondelete="RESTRICT"), nullable=True
    )
    outcome_observation_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_observations.id", ondelete="RESTRICT"), nullable=True
    )
    would_wear: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    would_buy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc, index=True)
    recorded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class LLMInvocation(Base):
    """One durable latency, cache, success, and cost observation."""

    __tablename__ = "llm_invocations"
    __table_args__ = (
        CheckConstraint("latency_ms >= 0"),
        CheckConstraint("estimated_cost_usd IS NULL OR estimated_cost_usd >= 0"),
        CheckConstraint("prompt_tokens IS NULL OR prompt_tokens >= 0"),
        CheckConstraint("completion_tokens IS NULL OR completion_tokens >= 0"),
        CheckConstraint("total_tokens IS NULL OR total_tokens >= 0"),
        CheckConstraint("provider_cost_usd IS NULL OR provider_cost_usd >= 0"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.id", ondelete="RESTRICT"), index=True
    )
    impression_id: Mapped[str | None] = mapped_column(
        ForeignKey("recommendation_impressions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    operation: Mapped[str] = mapped_column(String(50))
    prompt_version: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(200))
    latency_ms: Mapped[int] = mapped_column(Integer)
    cache_hit: Mapped[bool] = mapped_column(Boolean)
    succeeded: Mapped[bool] = mapped_column(Boolean)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc, index=True)


class PilotOperationalEvent(Base):
    """A connectivity failure or manual recovery observed during the pilot."""

    __tablename__ = "pilot_operational_events"
    __table_args__ = (
        CheckConstraint("event_type IN ('CONNECTIVITY_FAILURE', 'MANUAL_RECOVERY')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.id", ondelete="RESTRICT"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(30))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(default=now_naive_utc, index=True)
    recorded_by: Mapped[str] = mapped_column(String(255))
