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
