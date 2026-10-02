"""Manager review of a submitted house record: adopt it as evidence, or decline it.

Adopting answers two questions per ADR-006 and ADR-012:

- Which catalog version does the house's statement describe? Either an
  existing live ``Fragrance`` or a new one built from the house's own values.
- Which of the house's facts does the manager accept? Each accepted fact is
  listed in ``SourceSnapshot.fields``; only launch year and gender target may
  also change the catalog. A different name, brand, or concentration means a
  different version, never a correction to apply in place.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from fragrance_rater.core.vocabulary import GenderTarget
from fragrance_rater.schemas.house_intake import HouseSubmissionResponse

ConfirmableField = Literal[
    "name", "brand", "concentration", "launch_year", "gender_target"
]
UpdatableField = Literal["launch_year", "gender_target"]
Comparison = Literal["same", "differs", "house_silent"]

#: Facts in the order a reviewer reads them.
CONFIRMABLE_FIELDS: tuple[ConfirmableField, ...] = (
    "name",
    "brand",
    "concentration",
    "launch_year",
    "gender_target",
)
#: Facts whose difference means "this is another version", not "fix the row".
IDENTITY_FIELDS: frozenset[ConfirmableField] = frozenset(
    {"name", "brand", "concentration"}
)


class StrictInput(BaseModel):
    """Reject unrecognized fields."""

    model_config = ConfigDict(extra="forbid")


class ProposedFacts(BaseModel):
    """The house's facts, expressed in catalog terms."""

    name: str
    brand: str
    concentration: str | None
    launch_year: int | None
    gender_target: GenderTarget | None


class CatalogCandidate(BaseModel):
    """A live catalog version the submission might describe."""

    id: str
    name: str
    brand: str
    concentration: str
    version_key: str
    launch_year: int | None
    gender_target: str
    primary_family: str
    subfamily: str
    comparison: dict[ConfirmableField, Comparison]


class ReviewContext(BaseModel):
    """Everything a manager needs to decide on one submission."""

    submission: HouseSubmissionResponse
    proposed: ProposedFacts
    candidates: list[CatalogCandidate]


class ExistingTarget(StrictInput):
    """Adopt against a catalog version that already exists."""

    kind: Literal["existing"]
    fragrance_id: str = Field(min_length=1, max_length=36)


class NewTarget(StrictInput):
    """Add a catalog version built from the house's values.

    Only what a house cannot supply is asked of the manager: the version key,
    the Edwards family (``core.vocabulary.UNCLASSIFIED_FAMILY`` when no
    Edwards family fits, per ADR-014), and a gender target when the house did
    not state one.
    """

    kind: Literal["new"]
    version_key: str = Field(min_length=1, max_length=200)
    primary_family: str = Field(min_length=1, max_length=50)
    subfamily: str = Field(min_length=1, max_length=50)
    gender_target: GenderTarget | None = None

    @field_validator("version_key", "primary_family", "subfamily")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "cannot be blank"
            raise ValueError(msg)
        return value.strip()


class AdoptInput(StrictInput):
    """A manager's decision to adopt a submission as evidence."""

    target: Annotated[ExistingTarget | NewTarget, Field(discriminator="kind")]
    confirmed_fields: list[ConfirmableField] = Field(default_factory=list)
    apply_updates: list[UpdatableField] = Field(default_factory=list)
    record_perfumers: bool = False
    review_note: str | None = Field(default=None, max_length=2000)


class DeclineInput(StrictInput):
    """A manager's decision not to adopt a submission."""

    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "Give the house a reason"
            raise ValueError(msg)
        return value.strip()
