"""Unit tests for prediction schemas' outcome-link validation.

`PredictionOutcomeInput` must reject an empty string the same way it rejects
an omitted field: an empty string is falsy (satisfying the XOR check the
same way `None` would) but is a non-NULL value once persisted, which would
otherwise violate `PredictionSnapshot`'s "at most one outcome id" CHECK
constraint at flush time instead of failing cleanly here as a 422.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fragrance_rater.schemas.prediction import PredictionCreate, PredictionOutcomeInput


def test_exactly_one_outcome_id_is_required() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        PredictionOutcomeInput()
    with pytest.raises(ValidationError, match="exactly one"):
        PredictionOutcomeInput(outcome_evaluation_id="e1", outcome_observation_id="o1")
    assert (
        PredictionOutcomeInput(outcome_evaluation_id="e1").outcome_evaluation_id == "e1"
    )
    assert (
        PredictionOutcomeInput(outcome_observation_id="o1").outcome_observation_id
        == "o1"
    )


def test_empty_string_outcome_id_is_rejected_not_treated_as_absent() -> None:
    """An empty string must not slip past the XOR check as a falsy `None`-alike."""
    with pytest.raises(ValidationError):
        PredictionOutcomeInput(outcome_evaluation_id="", outcome_observation_id="o1")
    with pytest.raises(ValidationError):
        PredictionOutcomeInput(outcome_evaluation_id="e1", outcome_observation_id="")
    with pytest.raises(ValidationError):
        PredictionOutcomeInput(outcome_evaluation_id="", outcome_observation_id="")


def test_empty_string_checkpoint_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PredictionCreate(
            reviewer_id="r1",
            fragrance_id="f1",
            checkpoint_id="",
            model_id="m",
            model_version="v1",
        )


def _create(**overrides: object) -> PredictionCreate:
    defaults: dict[str, object] = {
        "reviewer_id": "r1",
        "fragrance_id": "f1",
        "model_id": "m",
        "model_version": "v1",
    }
    return PredictionCreate(**{**defaults, **overrides})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("predicted_rating", float("nan")),
        ("predicted_rating", float("inf")),
        ("uncertainty", float("inf")),
        ("percentile_rank", float("nan")),
    ],
)
def test_non_finite_floats_are_rejected(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        _create(**{field: value})


def test_predicted_rating_must_fit_a_numeric_predicted_scale() -> None:
    with pytest.raises(ValidationError, match="outside predicted_scale"):
        _create(predicted_rating=7.0, predicted_scale="1-5")
    # In bounds is accepted.
    assert _create(predicted_rating=4.0, predicted_scale="1-5").predicted_rating == 4.0
    assert _create(predicted_rating=7.5, predicted_scale="0-10").predicted_rating == 7.5


def test_a_non_numeric_predicted_scale_skips_range_validation() -> None:
    """A scale label that isn't `"<low>-<high>"` is trusted, not rejected."""
    assert (
        _create(predicted_rating=999, predicted_scale="percentile").predicted_rating
        == 999
    )


def test_oneof_constraint_is_published_in_the_generated_schema() -> None:
    """Each of the two `oneOf` branches must require its own outcome id field and
    exclude the other, matching `require_exactly_one_outcome` exactly; a bug that
    swaps, duplicates, or empties a branch must fail this test."""
    schema = PredictionOutcomeInput.model_json_schema()
    assert "oneOf" in schema
    branches = schema["oneOf"]
    assert len(branches) == 2
    evaluation_branch = next(
        branch
        for branch in branches
        if branch.get("required") == ["outcome_evaluation_id"]
    )
    observation_branch = next(
        branch
        for branch in branches
        if branch.get("required") == ["outcome_observation_id"]
    )
    # The two branches found above must actually be distinct objects, not
    # the same branch matched twice (which would happen if one was empty).
    assert evaluation_branch is not observation_branch
    assert evaluation_branch["not"] == {"required": ["outcome_observation_id"]}
    assert observation_branch["not"] == {"required": ["outcome_evaluation_id"]}
    # The top-level schema must not also carry a blanket "required" that
    # would make both ids independently mandatory alongside the oneOf.
    assert "required" not in schema
