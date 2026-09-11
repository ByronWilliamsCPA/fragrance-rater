"""Unit tests for evaluation schemas, focused on PATCH null/omit semantics.

`EvaluationUpdate` must distinguish "field omitted" (leave unchanged) from
"field explicitly set to null" on a per-field basis, matching each field's
underlying column nullability in `fragrance_rater.models.evaluation`:

- `rating` backs a NOT NULL column: omission is fine, explicit null must be
  rejected.
- `notes`, `longevity_rating`, `sillage_rating` back nullable columns:
  omission leaves the field unchanged, explicit null legitimately clears it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fragrance_rater.schemas.evaluation import EvaluationCreate, EvaluationUpdate


class TestEvaluationUpdateOmittedFields:
    """Fields left out of the payload must not appear in `model_fields_set`."""

    def test_omitting_all_fields_yields_empty_update(self) -> None:
        """An empty PATCH body means 'change nothing'."""
        data = EvaluationUpdate()

        assert data.model_dump(exclude_unset=True) == {}

    def test_omitting_rating_leaves_it_unset(self) -> None:
        """Omitting `rating` must not synthesize a null update for it."""
        data = EvaluationUpdate(notes="Great longevity")

        dumped = data.model_dump(exclude_unset=True)

        assert dumped == {"notes": "Great longevity"}
        assert "rating" not in dumped


class TestEvaluationUpdateNullableFields:
    """`notes`, `longevity_rating`, `sillage_rating` back nullable columns."""

    @pytest.mark.parametrize(
        "field_name",
        ["notes", "longevity_rating", "sillage_rating"],
    )
    def test_explicit_null_clears_nullable_field(self, field_name: str) -> None:
        """Explicit `null` for a nullable-backed field is accepted as-is."""
        data = EvaluationUpdate.model_validate({field_name: None})

        dumped = data.model_dump(exclude_unset=True)

        assert dumped == {field_name: None}


class TestEvaluationUpdateNonNullableRating:
    """`rating` backs a NOT NULL column and must reject explicit null."""

    def test_explicit_null_rating_is_rejected(self) -> None:
        """`{"rating": null}` must fail validation, not reach the service."""
        with pytest.raises(ValidationError) as exc_info:
            EvaluationUpdate.model_validate({"rating": None})

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("rating",) for error in errors)

    def test_valid_rating_value_is_accepted(self) -> None:
        """A real rating value still validates and updates normally."""
        data = EvaluationUpdate.model_validate({"rating": 4})

        assert data.model_dump(exclude_unset=True) == {"rating": 4}

    def test_out_of_range_rating_still_rejected(self) -> None:
        """The null guard must not weaken the existing 1-5 range check."""
        with pytest.raises(ValidationError):
            EvaluationUpdate.model_validate({"rating": 6})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-09-10T12:00:00-07:00", "2026-09-10T19:00:00"),
        ("2026-09-10T19:00:00Z", "2026-09-10T19:00:00"),
        ("2026-09-10T19:00:00", "2026-09-10T19:00:00"),
        (None, None),
    ],
)
def test_encounter_dates_use_naive_utc(value, expected):
    """Offsets normalize; legacy naive UTC and omitted encounter times remain valid."""
    data = EvaluationCreate(
        fragrance_id="fragrance", reviewer_id="reviewer", rating=3, evaluated_at=value
    )
    actual = data.evaluated_at.isoformat() if data.evaluated_at else None
    assert actual == expected
