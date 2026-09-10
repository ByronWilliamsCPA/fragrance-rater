"""Unit tests for fragrance schemas, focused on PATCH null/omit semantics.

`FragranceUpdate` must distinguish "field omitted" (leave unchanged) from
"field explicitly set to null" on a per-field basis, matching each field's
underlying column nullability in `fragrance_rater.models.fragrance.Fragrance`:

- `name`, `brand`, `concentration`, `gender_target`, `primary_family`,
  `subfamily` back NOT NULL columns: omission is fine, explicit null must
  be rejected.
- `launch_year`, `intensity` back nullable columns: omission leaves the
  field unchanged, explicit null legitimately clears it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fragrance_rater.schemas.fragrance import FragranceUpdate

NON_NULLABLE_FIELDS = [
    ("name", "Aventus"),
    ("brand", "Creed"),
    ("concentration", "EDP"),
    ("gender_target", "Masculine"),
    ("primary_family", "Woody"),
    ("subfamily", "Aromatic"),
]

NULLABLE_FIELDS = ["launch_year", "intensity"]


class TestFragranceUpdateOmittedFields:
    """Fields left out of the payload must not appear in `model_fields_set`."""

    def test_omitting_all_fields_yields_empty_update(self) -> None:
        """An empty PATCH body means 'change nothing'."""
        data = FragranceUpdate()

        assert data.model_dump(exclude_unset=True) == {}

    def test_omitting_a_field_leaves_it_unset(self) -> None:
        """Omitting a field must not synthesize a null update for it."""
        data = FragranceUpdate(name="Aventus")

        dumped = data.model_dump(exclude_unset=True)

        assert dumped == {"name": "Aventus"}
        assert "brand" not in dumped


class TestFragranceUpdateNullableFields:
    """`launch_year` and `intensity` back nullable columns."""

    @pytest.mark.parametrize("field_name", NULLABLE_FIELDS)
    def test_explicit_null_clears_nullable_field(self, field_name: str) -> None:
        """Explicit `null` for a nullable-backed field is accepted as-is."""
        data = FragranceUpdate.model_validate({field_name: None})

        dumped = data.model_dump(exclude_unset=True)

        assert dumped == {field_name: None}


class TestFragranceUpdateNonNullableFields:
    """`name`, `brand`, `concentration`, `gender_target`, `primary_family`,
    and `subfamily` back NOT NULL columns and must reject explicit null.
    """

    @pytest.mark.parametrize(("field_name", "_valid_value"), NON_NULLABLE_FIELDS)
    def test_explicit_null_is_rejected(
        self, field_name: str, _valid_value: str
    ) -> None:
        """An explicit null must fail validation, not reach the service."""
        with pytest.raises(ValidationError) as exc_info:
            FragranceUpdate.model_validate({field_name: None})

        errors = exc_info.value.errors()
        assert any(error["loc"] == (field_name,) for error in errors)

    @pytest.mark.parametrize(("field_name", "valid_value"), NON_NULLABLE_FIELDS)
    def test_valid_value_is_accepted(self, field_name: str, valid_value: str) -> None:
        """A real value for the field still validates and updates normally."""
        data = FragranceUpdate.model_validate({field_name: valid_value})

        assert data.model_dump(exclude_unset=True) == {field_name: valid_value}
