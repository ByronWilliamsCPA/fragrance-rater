"""Request and response contracts for ML prediction snapshots."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Recognizes a `"<low>-<high>"` scale label (e.g. "0-10", "1-5"). Scales that
# don't match this shape (e.g. a named percentile band) skip range
# validation below rather than being rejected outright.
_NUMERIC_SCALE = re.compile(r"^(-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)$")


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
    # `allow_inf_nan=False` on all three: a frozen prediction is meant to be
    # compared numerically against a later outcome, so NaN/Infinity (which
    # PostgreSQL's `Float` happily stores) would silently poison that
    # comparison rather than fail loudly at the API boundary.
    predicted_rating: float | None = Field(default=None, allow_inf_nan=False)
    uncertainty: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    percentile_rank: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )
    scenario: str | None = Field(default=None, max_length=100)
    input_manifest: list[dict[str, object]] = Field(default_factory=list)
    explanation: dict[str, object] | None = None

    @model_validator(mode="after")
    def require_rating_within_declared_scale(self) -> PredictionCreate:
        """Reject a predicted_rating outside its own declared predicted_scale.

        Only enforced when `predicted_scale` parses as `"<low>-<high>"`
        (covers the "0-10"/"1-5" scales this system actually uses); a scale
        label that doesn't match that shape is trusted as-is rather than
        rejected, since this schema doesn't own an exhaustive scale registry.
        """
        if self.predicted_rating is None:
            return self
        match = _NUMERIC_SCALE.match(self.predicted_scale)
        if match is None:
            return self
        low, high = (float(match.group(1)), float(match.group(2)))
        if not low <= self.predicted_rating <= high:
            message = (
                f"predicted_rating {self.predicted_rating} is outside "
                f"predicted_scale {self.predicted_scale!r}"
            )
            raise ValueError(message)
        return self


def _require_exactly_one_outcome_schema(schema: dict[str, Any]) -> None:
    """Publish the exactly-one-of-two-fields rule the model_validator enforces.

    Kept as a schema decoration rather than a discriminated union so the
    request stays a flat, simple two-field shape at runtime; this only
    changes what a spec-driven client generator sees. Each `oneOf` branch
    both requires its own field and forbids the other, matching the
    validator below exactly: `{}`, both fields, or either field alone with
    the other explicitly present are all excluded.
    """
    schema["oneOf"] = [
        {
            "required": ["outcome_evaluation_id"],
            "not": {"required": ["outcome_observation_id"]},
        },
        {
            "required": ["outcome_observation_id"],
            "not": {"required": ["outcome_evaluation_id"]},
        },
    ]
    schema.pop("required", None)


class PredictionOutcomeInput(BaseModel):
    """Link a frozen prediction to the observation that later confirmed or refuted it.

    Exactly one of ``outcome_evaluation_id`` (an ordinary encounter) or
    ``outcome_observation_id`` (a controlled observation) is required; the
    other must be omitted or explicitly null. Both empty (`{}`) and both set
    are rejected, and the generated OpenAPI schema's ``oneOf`` publishes
    that same rule (see ``_require_exactly_one_outcome_schema``) rather than
    showing both properties as merely optional.
    """

    model_config = ConfigDict(
        extra="forbid", json_schema_extra=_require_exactly_one_outcome_schema
    )

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
    ``outcome_observation_id``, ``outcome_linked_at``, and
    ``outcome_recorded_by``, which start NULL and are set exactly once by a
    later, separate outcome-link call.
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
