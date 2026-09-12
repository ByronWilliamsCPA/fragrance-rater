"""Validated protocol inputs and independent unipolar response scales."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from fragrance_rater.utils.gtin import is_valid_gtin

Role = Literal[
    "UNIVERSAL_BASELINE",
    "HIDDEN_REPEAT",
    "HOLDOUT",
    "ACTIVE_LEARNING",
    "RETEST",
    "OWNED_VALIDATION",
    "OTHER",
]
Stage = Literal["BLOTTER", "SKIN"]


class StrictInput(BaseModel):
    """Reject unrecognized fields rather than silently losing responses."""

    model_config = ConfigDict(extra="forbid")


class ProgramInput(StrictInput):
    """Versioned program definition."""

    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=10000)


class MembershipInput(StrictInput):
    """Require exact catalog ID and documented identity verification."""

    fragrance_id: str
    role: Role
    repeat_of_id: str | None = None
    group_name: str = Field(default="Baseline", min_length=1, max_length=200)
    selection: dict[str, str | float | None] = Field(default_factory=dict)
    identity_evidence: str = Field(min_length=1, max_length=2000)
    # #ASSUME: data-integrity: gtin is optional (a decant, a vintage
    # sample, or some indie houses carry no scannable manufacturer
    # barcode) but when given must be a real, check-digit-valid GTIN -
    # the strongest identity signal this project has, since it is
    # assigned per exact SKU and does not depend on any scraped source
    # being unambiguous. CalibrationService.add_member additionally
    # cross-checks it against the fragrance's own scraped source
    # evidence, when one exists, before accepting it.
    # #VERIFY: covered by schema tests (valid/invalid check digit) and a
    # service-level test for the cross-check.
    gtin: str | None = Field(default=None, min_length=8, max_length=14)

    @field_validator("gtin")
    @classmethod
    def _validate_gtin(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_gtin(value):
            msg = "gtin must be a valid GTIN-8/12/13/14 (GS1 check digit)"
            raise ValueError(msg)
        return value


class EnrollmentInput(StrictInput):
    """Recorder identity is independent of whose palate is measured."""

    reviewer_id: str
    recorder_usernames: list[str] = Field(min_length=1, max_length=20)
    session_size: int = Field(default=3, ge=1, le=20)


class SkinPlanInput(StrictInput):
    """Explicit reason, including low confidence or low-rated controls."""

    reason: str = Field(min_length=1, max_length=2000)


class ResponseInput(StrictInput):
    """A submitted timepoint; null means unanswered, zero is a response."""

    stage: Stage
    elapsed_minutes: int = Field(default=0, ge=0, le=100000)
    detected: bool | None = None
    intensity: int | None = Field(default=None, ge=0, le=5)
    liking: int | None = Field(default=None, ge=0, le=10)
    confidence: int | None = Field(default=None, ge=0, le=5)
    sweetness: int | None = Field(default=None, ge=0, le=5)
    freshness: int | None = Field(default=None, ge=0, le=5)
    density: int | None = Field(default=None, ge=0, le=5)
    familiarity: int | None = Field(default=None, ge=0, le=5)
    dryness: int | None = Field(default=None, ge=0, le=5)
    clean_soapy: int | None = Field(default=None, ge=0, le=5)
    earthy_rooty: int | None = Field(default=None, ge=0, le=5)
    bodily_animalic: int | None = Field(default=None, ge=0, le=5)
    discomfort: int | None = Field(default=None, ge=0, le=5)
    opening_liking: int | None = Field(default=None, ge=0, le=10)
    drydown_liking: int | None = Field(default=None, ge=0, le=10)
    would_wear: int | None = Field(default=None, ge=0, le=10)
    would_buy: int | None = Field(default=None, ge=0, le=10)
    artistic_appreciation: int | None = Field(default=None, ge=0, le=10)
    projection: int | None = Field(default=None, ge=0, le=5)
    longevity_minutes: int | None = Field(default=None, ge=0, le=100000)
    perceived_notes: list[str] | None = Field(default=None, max_length=50)
    likes: str | None = Field(default=None, max_length=2000)
    dislikes: str | None = Field(default=None, max_length=2000)
    reminds_me_of: str | None = Field(default=None, max_length=2000)
    comments: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_detection(self) -> "ResponseInput":
        """Reject neutral liking or missing intensity for non-detection."""
        if self.detected is False and (self.intensity != 0 or self.liking is not None):
            message = "Non-detection requires intensity 0 and liking null"
            raise ValueError(message)
        return self


class CheckpointInput(StrictInput):
    """External model outputs retain their actual units and algorithm."""

    algorithm_version: str = Field(min_length=1, max_length=200)
    predictions: list[dict[str, str | float | None]] = Field(default_factory=list)
