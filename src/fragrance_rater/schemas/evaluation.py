"""Pydantic schemas for evaluation-related API models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class EvaluationCreate(BaseModel):
    """Schema for creating a new evaluation."""

    fragrance_id: str = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)
    rating: int = Field(..., ge=1, le=5)
    notes: str | None = Field(None, max_length=2000)
    longevity_rating: int | None = Field(None, ge=1, le=5)
    sillage_rating: int | None = Field(None, ge=1, le=5)


class EvaluationUpdate(BaseModel):
    """Schema for updating an evaluation (PATCH semantics).

    Every field defaults to `None` so a client can omit it to mean "leave
    unchanged"; `evaluation_service.update()` reads only the fields present
    in the request via `model_dump(exclude_unset=True)`. `notes`,
    `longevity_rating`, and `sillage_rating` back nullable columns
    (`Evaluation.notes`/`longevity_rating`/`sillage_rating`), so an explicit
    `null` for one of those is legitimate and clears it. `rating` backs a
    NOT NULL column and is additionally guarded below so an explicit `null`
    is rejected rather than reaching the database layer.
    """

    rating: int | None = Field(None, ge=1, le=5)
    notes: str | None = Field(None, max_length=2000)
    longevity_rating: int | None = Field(None, ge=1, le=5)
    sillage_rating: int | None = Field(None, ge=1, le=5)

    # #CRITICAL: data-integrity: `rating` backs `Evaluation.rating`, a NOT
    # NULL column. The field is typed `int | None` only so the client can
    # omit it from a PATCH body to mean "leave unchanged"; without this
    # validator, an explicit `{"rating": null}` would pass the `ge`/`le`
    # constraints (Pydantic skips them for `None`), survive
    # `exclude_unset=True` (the key *was* present in the request), and
    # reach `evaluation_service.update()`'s `setattr(evaluation, "rating",
    # None)`, failing only at DB flush with a raw IntegrityError instead of
    # a clean 422.
    # #VERIFY: Pydantic v2 does not run field validators against a field's
    # default value (only against values actually supplied in the input),
    # so omitting `rating` entirely still reaches `evaluation_service.py`
    # without tripping this check; see
    # tests/unit/test_schemas/test_evaluation.py.
    @field_validator("rating")
    @classmethod
    def _reject_null_rating(cls, value: int | None) -> int:
        """Reject an explicit `null` for the non-nullable `rating` field.

        Args:
            value (int | None): The rating supplied by the client. Only
                called when the client actually included `rating` in the
                request; omitted fields never reach this validator.

        Returns:
            int: The validated rating, unchanged.

        Raises:
            ValueError: If the client explicitly set `rating` to `null`.
        """
        if value is None:
            msg = "rating cannot be null; omit the field to leave it unchanged"
            raise ValueError(msg)
        return value


class EvaluationResponse(BaseModel):
    """Schema for evaluation response."""

    id: str
    fragrance_id: str
    reviewer_id: str
    rating: int
    notes: str | None
    longevity_rating: int | None
    sillage_rating: int | None
    evaluated_at: datetime
    created_at: datetime
    # Critical finding 2: Authentik username of whoever was logged in when
    # this evaluation was submitted. Independent of reviewer_id; None when
    # no Authentik identity was available (e.g. local dev, seeded data).
    recorded_by: str | None = None

    model_config = {"from_attributes": True}
