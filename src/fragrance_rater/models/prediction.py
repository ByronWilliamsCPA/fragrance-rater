"""Frozen model predictions, checked against real outcomes after the fact.

Supports ML testing that refines recommendation/liking projections: a model
predicts a rating for one evaluator/fragrance pair *before* the real
encounter exists, the prediction is frozen immediately (ADR-009's
prospective-evaluation principle), and later exactly one real outcome is
linked to it so prediction error can be measured honestly. Distinct from
``ModelCheckpoint`` (a per-enrollment, per-calibration-program snapshot) and
from ``RecommendationImpression`` (a ranked candidate shown to an
evaluator): a ``PredictionSnapshot`` is a standalone, model-agnostic record
of "this model predicted this rating," usable whether or not a calibration
program or a recommendation run is involved.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from fragrance_rater.core.database import Base
from fragrance_rater.utils.timestamps import now_naive_utc


def identifier() -> str:
    """Return a new opaque identifier."""
    return str(uuid4())


class PredictionSnapshot(Base):
    """A model's predicted rating for one evaluator/fragrance, frozen up front.

    ``predicted_rating``, ``uncertainty``, ``percentile_rank``,
    ``input_manifest``, and ``explanation`` are set once at creation and
    never recomputed in place — the point of freezing a prediction is that
    it cannot quietly change to match what actually happened. The
    ``outcome_*`` columns are the one documented exception: they start NULL
    and are set exactly once, after a real outcome exists, by
    ``PredictionService.link_outcome()``. That call never touches the
    predicted values above; it only records which later observation the
    prediction is being measured against.
    """

    __tablename__ = "prediction_snapshots"
    __table_args__ = (
        CheckConstraint("uncertainty IS NULL OR uncertainty >= 0"),
        CheckConstraint(
            "percentile_rank IS NULL OR (percentile_rank >= 0 AND percentile_rank <= 100)"
        ),
        CheckConstraint(
            "NOT (outcome_evaluation_id IS NOT NULL AND outcome_observation_id IS NOT NULL)"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("reviewers.id", ondelete="RESTRICT"), index=True
    )
    fragrance_id: Mapped[str] = mapped_column(
        ForeignKey("fragrances.id", ondelete="RESTRICT"), index=True
    )
    # Optional: set when this prediction was produced as part of a
    # calibration program's checkpoint. NULL for predictions tested against
    # ordinary history outside any calibration enrollment.
    checkpoint_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_checkpoints.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Two fields rather than one `algorithm_version` string (contrast
    # RecommendationRun/ModelCheckpoint, which score with one deterministic,
    # versioned algorithm): ML testing is expected to compare multiple
    # candidate model families side by side, so the family/approach
    # identifier and its version must be independently filterable.
    model_id: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(100))
    feature_snapshot_version: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    # `predicted_scale` documents what `predicted_rating` means (e.g.
    # "0-10" to match controlled `liking`, "1-5" to match ordinary
    # `rating`) rather than hard-coding one scale at the database level.
    predicted_scale: Mapped[str] = mapped_column(
        String(20), default="0-10", server_default="0-10"
    )
    predicted_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentile_rank: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Free-text scenario tag for a scenario-specific prediction; the full
    # controlled scenario/context domain is a separate, larger schema
    # change (see docs/planning/data-model-gap-analysis.md §XX-XXIX) and is
    # deliberately not built out here.
    scenario: Mapped[str | None] = mapped_column(String(100), nullable=True)

    input_manifest: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    explanation: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=now_naive_utc, index=True)
    recorded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Append-only outcome link; see class docstring.
    outcome_evaluation_id: Mapped[str | None] = mapped_column(
        ForeignKey("evaluations.id", ondelete="RESTRICT"), nullable=True
    )
    outcome_observation_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_observations.id", ondelete="RESTRICT"), nullable=True
    )
    outcome_linked_at: Mapped[datetime | None] = mapped_column(
        nullable=True, default=None
    )
    outcome_recorded_by: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )
