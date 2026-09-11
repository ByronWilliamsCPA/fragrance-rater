"""Pydantic schemas for fragrance-related API models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from fragrance_rater.core.vocabulary import GenderTarget


class NoteCreate(BaseModel):
    """Schema for creating a new note."""

    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=50)
    subcategory: str | None = Field(None, max_length=50)


class NoteResponse(BaseModel):
    """Schema for note response."""

    id: str
    name: str
    category: str
    subcategory: str | None

    model_config = {"from_attributes": True}


class FragranceNoteCreate(BaseModel):
    """Schema for creating a fragrance-note association."""

    note_name: str = Field(..., min_length=1, max_length=100)
    note_category: str = Field(..., min_length=1, max_length=50)
    position: Literal["top", "heart", "flat", "base"]


class FragranceNoteResponse(BaseModel):
    """Schema for fragrance-note response."""

    note: NoteResponse
    position: str

    model_config = {"from_attributes": True}


class FragranceAccordCreate(BaseModel):
    """Schema for creating a fragrance accord."""

    accord_type: str = Field(..., min_length=1, max_length=50)
    intensity: float = Field(..., ge=0.0, le=1.0)


class FragranceAccordResponse(BaseModel):
    """Schema for fragrance accord response."""

    accord_type: str
    intensity: float

    model_config = {"from_attributes": True}


class FragranceCreate(BaseModel):
    """Schema for creating a new fragrance."""

    name: str = Field(..., min_length=1, max_length=255)
    brand: str = Field(..., min_length=1, max_length=255)
    concentration: str = Field(..., min_length=1, max_length=50)
    version_key: str = Field(default="legacy", min_length=1, max_length=200)
    launch_year: int | None = Field(None, ge=1800, le=2100)
    gender_target: GenderTarget = "Unisex"
    primary_family: str = Field(..., min_length=1, max_length=50)
    subfamily: str = Field(..., min_length=1, max_length=50)
    intensity: str | None = Field(None, max_length=20)
    notes: list[FragranceNoteCreate] = Field(default_factory=list)
    accords: list[FragranceAccordCreate] = Field(default_factory=list)


class FragranceUpdate(BaseModel):
    """Schema for updating a fragrance (PATCH semantics).

    Every field defaults to `None` so a client can omit it to mean "leave
    unchanged"; `fragrance_service.update()` reads only the fields present
    in the request via `model_dump(exclude_unset=True)`. `launch_year` and
    `intensity` back nullable columns (`Fragrance.launch_year`/`intensity`),
    so an explicit `null` for one of those is legitimate and clears it.
    `name`, `brand`, `concentration`, `gender_target`, `primary_family`, and
    `subfamily` all back NOT NULL columns and are additionally guarded below
    so an explicit `null` for any of them is rejected rather than reaching
    the database layer.
    """

    name: str | None = Field(None, min_length=1, max_length=255)
    brand: str | None = Field(None, min_length=1, max_length=255)
    concentration: str | None = Field(None, min_length=1, max_length=50)
    launch_year: int | None = Field(None, ge=1800, le=2100)
    gender_target: GenderTarget | None = None
    primary_family: str | None = Field(None, min_length=1, max_length=50)
    subfamily: str | None = Field(None, min_length=1, max_length=50)
    intensity: str | None = Field(None, max_length=20)

    # #CRITICAL: data-integrity: `name`, `brand`, `concentration`,
    # `gender_target`, `primary_family`, and `subfamily` all back NOT NULL
    # columns on `Fragrance`. Each field is typed as `X | None` only so the
    # client can omit it from a PATCH body to mean "leave unchanged";
    # without this validator, an explicit `{"name": null}` (etc.) would
    # pass the length/Literal constraints (Pydantic skips them for `None`),
    # survive `exclude_unset=True` (the key *was* present in the request),
    # and reach `fragrance_service.update()`'s `setattr(fragrance, field,
    # None)`, failing only at DB flush with a raw IntegrityError instead of
    # a clean 422.
    # #VERIFY: Pydantic v2 does not run field validators against a field's
    # default value (only against values actually supplied in the input),
    # so omitting any of these fields still reaches `fragrance_service.py`
    # without tripping this check; `launch_year` and `intensity` are
    # deliberately excluded from this list because they back nullable
    # columns and an explicit `null` is the correct way to clear them. See
    # tests/unit/test_schemas/test_fragrance.py.
    @field_validator(
        "name",
        "brand",
        "concentration",
        "gender_target",
        "primary_family",
        "subfamily",
    )
    @classmethod
    def _reject_null_for_required_field(
        cls, value: object, info: ValidationInfo
    ) -> object:
        """Reject an explicit `null` for fields backed by NOT NULL columns.

        Args:
            value (object): The value supplied by the client for the field
                currently being validated. Only called when the client
                actually included that field in the request; omitted
                fields never reach this validator.
            info (ValidationInfo): Pydantic validation context; used only
                to name the offending field in the error message.

        Returns:
            object: The validated value, unchanged.

        Raises:
            ValueError: If the client explicitly set the field to `null`.
        """
        if value is None:
            msg = (
                f"{info.field_name} cannot be null; "
                "omit the field to leave it unchanged"
            )
            raise ValueError(msg)
        return value


class FragranceResponse(BaseModel):
    """Schema for fragrance response."""

    id: str
    name: str
    brand: str
    concentration: str
    launch_year: int | None
    gender_target: str
    primary_family: str
    subfamily: str
    intensity: str | None
    data_source: str
    external_id: str | None
    created_at: datetime
    updated_at: datetime
    notes: list[FragranceNoteResponse] = Field(default_factory=list)
    accords: list[FragranceAccordResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class FragranceSearchParams(BaseModel):
    """Schema for fragrance search parameters."""

    q: str | None = Field(None, description="Search query for name or brand")
    brand: str | None = Field(None, description="Filter by brand")
    primary_family: str | None = Field(None, description="Filter by fragrance family")
    gender_target: GenderTarget | None = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
