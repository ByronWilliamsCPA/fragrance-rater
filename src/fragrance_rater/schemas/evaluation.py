"""Pydantic schemas for evaluation-related API models."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator, model_validator

WORN_BY_REVIEWER_ID_DESCRIPTION = (
    "ADR-011: reviewer the fragrance was worn by, when this rating is an "
    '"on others" opinion (e.g. a partner\'s reaction) rather than "on me". '
    "Omit or leave null for the default self-worn rating. Must differ from "
    "reviewer_id."
)


class EvaluationCreate(BaseModel):
    """Schema for creating a new evaluation."""

    fragrance_id: str = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)
    rating: int = Field(..., ge=1, le=5)
    notes: str | None = Field(None, max_length=2000)
    longevity_rating: int | None = Field(None, ge=1, le=5)
    sillage_rating: int | None = Field(None, ge=1, le=5)
    worn_by_reviewer_id: str | None = Field(
        None, min_length=1, description=WORN_BY_REVIEWER_ID_DESCRIPTION
    )

    evaluated_at: datetime | None = Field(
        None,
        description="Encounter time; timezone-naive inputs are interpreted as UTC.",
    )

    @field_validator("evaluated_at")
    @classmethod
    def normalize_encounter_time(cls, value: datetime | None) -> datetime | None:
        """Normalize supplied encounter times for the existing UTC database columns."""
        if value is None or value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: UP017 - Python 3.10

    # #ASSUME: data-integrity: `worn_by_reviewer_id` equal to `reviewer_id`
    # would be a redundant, ambiguous way to spell the default "on me"
    # rating (which is NULL), and would let two different stored shapes
    # mean the same thing to every later reader (recommendation scoring,
    # history display). Reject it here rather than silently normalizing it,
    # so a client mistake is visible instead of quietly collapsed.
    # #VERIFY: existence of `worn_by_reviewer_id` as a live reviewer is
    # checked at the API layer (api/evaluations.py), matching the existing
    # fragrance_id/reviewer_id pattern; Pydantic alone cannot query the
    # database.
    @model_validator(mode="after")
    def _reject_self_as_worn_by(self) -> EvaluationCreate:
        """Reject a redundant explicit self-reference for `worn_by_reviewer_id`."""
        if (
            self.worn_by_reviewer_id is not None
            and self.worn_by_reviewer_id == self.reviewer_id
        ):
            msg = (
                "worn_by_reviewer_id must differ from reviewer_id; "
                "omit it (or leave it null) for an on-me rating"
            )
            raise ValueError(msg)
        return self


class EvaluationUpdate(BaseModel):
    """Schema for updating an evaluation (PATCH semantics).

    Every field defaults to `None` so a client can omit it to mean "leave
    unchanged"; `evaluation_service.update()` reads only the fields present
    in the request via `model_dump(exclude_unset=True)`. `notes`,
    `longevity_rating`, `sillage_rating`, and `worn_by_reviewer_id` back
    nullable columns (`Evaluation.notes`/`longevity_rating`/
    `sillage_rating`/`worn_by_reviewer_id`), so an explicit `null` for one
    of those is legitimate: for `worn_by_reviewer_id` it reverts the rating
    to the default "on me" perspective. `rating` backs a NOT NULL column
    and is additionally guarded below so an explicit `null` is rejected
    rather than reaching the database layer.

    `worn_by_reviewer_id` cannot be validated against `reviewer_id` here
    (this schema has no `reviewer_id` field -- it is immutable via PATCH),
    so that self-reference check and the existence check both happen at
    the API layer (api/evaluations.py), which already has the stored
    evaluation's `reviewer_id` on hand.
    """

    rating: int | None = Field(None, ge=1, le=5)
    notes: str | None = Field(None, max_length=2000)
    longevity_rating: int | None = Field(None, ge=1, le=5)
    sillage_rating: int | None = Field(None, ge=1, le=5)
    worn_by_reviewer_id: str | None = Field(
        None, min_length=1, description=WORN_BY_REVIEWER_ID_DESCRIPTION
    )

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
    worn_by_reviewer_id: str | None = None
    evaluated_at: datetime
    created_at: datetime
    # Critical finding 2: Authentik username of whoever was logged in when
    # this evaluation was submitted. Independent of reviewer_id; None when
    # no Authentik identity was available (e.g. local dev, seeded data).
    recorded_by: str | None = None

    model_config = {"from_attributes": True}
