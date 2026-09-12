"""Request and response contracts for ML prediction snapshots."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PredictionCreate(BaseModel):
    """Freeze one model's predicted rating before the real outcome exists."""

    model_config = ConfigDict(extra="forbid")

    reviewer_id: str = Field(..., min_length=1)
    fragrance_id: str = Field(..., min_length=1)
    checkpoint_id: str | None = Field(default=None, min_length=1)
    model_id: str = Field(..., min_length=1, max_length=100)
    model_version: str = Field(..., min_length=1, max_length=100)
    feature_snapshot_version: str | None = Field(default=None, max_length=100)
    predicted_scale: str = Field(default="0-10", min_length=1, max_length=20)
    predicted_rating: float | None = None
    uncertainty: float | None = Field(default=None, ge=0)
    percentile_rank: float | None = Field(default=None, ge=0, le=100)
    scenario: str | None = Field(default=None, max_length=100)
    input_manifest: list[dict[str, object]] = Field(default_factory=list)
    explanation: dict[str, object] | None = None


class PredictionOutcomeInput(BaseModel):
    """Link a frozen prediction to the observation that later confirmed or refuted it.

    Exactly one of ``outcome_evaluation_id`` (an ordinary encounter) or
    ``outcome_observation_id`` (a controlled observation) is required; the
    other must be omitted or explicitly null. Both empty (`{}`) and both set
    are rejected. This is deliberately two plain optional fields rather than
    a discriminated union so the request stays a flat, simple shape; the
    generated OpenAPI schema will show both properties as optional even
    though a request choosing zero or two of them still returns 422 here.
    """

    model_config = ConfigDict(extra="forbid")

    # `min_length=1` matters as much as the model_validator below: without
    # it, an empty string is falsy (satisfying the XOR check below the same
    # way `None` would) but is still a non-NULL value once persisted, which
    # would violate PredictionSnapshot's "at most one outcome id set" CHECK
    # constraint at flush time instead of failing cleanly here as a 422.
    outcome_evaluation_id: str | None = Field(default=None, min_length=1)
    outcome_observation_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_exactly_one_outcome(self) -> PredictionOutcomeInput:
        """Reject an empty or doubly-linked outcome."""
        if bool(self.outcome_evaluation_id) == bool(self.outcome_observation_id):
            message = (
                "link exactly one of outcome_evaluation_id or outcome_observation_id"
            )
            raise ValueError(message)
        return self


class PredictionView(BaseModel):
    """Serialized, (mostly) immutable prediction snapshot.

    Every field is set once at creation except ``outcome_evaluation_id``,
    ``outcome_observation_id``, and ``outcome_linked_at``, which start NULL
    and are set exactly once by a later, separate outcome-link call.
    """

    id: str
    reviewer_id: str
    fragrance_id: str
    checkpoint_id: str | None
    model_id: str
    model_version: str
    feature_snapshot_version: str | None
    predicted_scale: str
    predicted_rating: float | None
    uncertainty: float | None
    percentile_rank: float | None
    scenario: str | None
    input_manifest: list[dict[str, object]]
    explanation: dict[str, object] | None
    created_at: datetime
    recorded_by: str | None
    outcome_evaluation_id: str | None
    outcome_observation_id: str | None
    outcome_linked_at: datetime | None
    outcome_recorded_by: str | None

    model_config = ConfigDict(from_attributes=True)
