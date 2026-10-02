"""Fragrance house intake: what a house may tell us about one of its fragrances.

The payload is shaped by two governing decisions:

- ADR-017 (and the olfactory vocabulary spec): a house is never asked to
  answer in this project's vocabulary. Notes, accords, and the family the
  house names are captured verbatim, with pyramid position and the house's
  own ordering, which is exactly the shape a later D1 ``declared_label`` row
  needs. Nothing here maps a house's words onto ``fr-core`` terms.
- ADR-012: a house's statement is manufacturer-provided evidence. It records
  who answered on the house's behalf and the use the house permits, so the
  reviewer can derive ``SourceSnapshot.permission_state`` without guessing.

A draft may be partial; :func:`submission_problems` is the stricter check a
draft must pass before it is submitted, so a house can save progress without
having every answer to hand.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from fragrance_rater.core.vocabulary import (
    EARLIEST_LAUNCH_YEAR,
    GenderTarget,
    MarketStatus,
)
from fragrance_rater.utils.gtin import is_valid_gtin

Concentration = Literal[
    "EDC", "EDT", "EDP", "PARFUM", "EXTRAIT", "OIL", "SOLID", "OTHER"
]
# Shared with the catalog (core/vocabulary.py) so a house's answer lands in a
# catalog column without translation.
Availability = MarketStatus
MarketedFor = GenderTarget | Literal["not_specified"]
NoteStructure = Literal["pyramid", "linear"]
NotePosition = Literal["top", "heart", "base", "unspecified"]
PermissionScope = Literal["retain_and_train", "retain_for_qc_only"]
SubmissionStatus = Literal["draft", "submitted"]
ReviewStatus = Literal["pending", "adopted", "declined", "superseded"]

#: How many years ahead an upcoming launch may be announced.
LAUNCH_YEAR_LEAD = 3

MAX_NOTES = 100
MAX_ACCORDS = 30
MAX_PERFUMERS = 10
MAX_GTINS = 20
#: Longest single note, accord, or perfumer name.
MAX_ENTRY_LENGTH = 200


def _require_text(value: str, label: str) -> str:
    """Reject blank text while keeping the house's own wording unchanged.

    # #ASSUME: data-integrity: ADR-017 layer 1 stores raw text verbatim and
    # never normalizes it, so this validator does not strip, case-fold, or
    # otherwise rewrite the value. The frontend trims outer whitespace before
    # sending; the server only refuses text that carries no content at all.
    # #VERIFY: test_house_intake_schemas asserts "Vanille de Madagascar" and
    # "Acqua di Giò" round-trip byte-for-byte.
    """
    if not value.strip():
        msg = f"{label} cannot be blank"
        raise ValueError(msg)
    return value


class DeclaredNote(BaseModel):
    """One note as the house names it, at the position the house gives it."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_ENTRY_LENGTH)
    position: NotePosition

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        return _require_text(value, "A note")


class HouseSubmissionPayload(BaseModel):
    """Everything a house can tell us about one fragrance, all optional in draft.

    The list order of ``notes``, ``accords``, and ``perfumers`` is the house's
    own order and is preserved; it becomes ``declared_label.source_order``.
    """

    model_config = ConfigDict(extra="forbid")

    # Identity: the facts ADR-012 asks a brand to confirm directly.
    fragrance_name: str = Field(min_length=1, max_length=255)
    line: str | None = Field(default=None, max_length=255)
    concentration: Concentration | None = None
    concentration_other: str | None = Field(default=None, max_length=100)
    version_label: str | None = Field(default=None, max_length=200)
    launch_year: int | None = None
    availability: Availability | None = None
    marketed_for: MarketedFor | None = None
    perfumers: list[str] = Field(default_factory=list, max_length=MAX_PERFUMERS)
    product_url: str | None = Field(default=None, max_length=1000)
    gtins: list[str] = Field(default_factory=list, max_length=MAX_GTINS)

    # Olfactory description in the house's own words (ADR-017 layer 1).
    note_structure: NoteStructure = "pyramid"
    notes: list[DeclaredNote] = Field(default_factory=list, max_length=MAX_NOTES)
    accords: list[str] = Field(default_factory=list, max_length=MAX_ACCORDS)
    family_as_described: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=4000)

    # Permission and attestation (ADR-012).
    permission_scope: PermissionScope | None = None
    contact_name: str | None = Field(default=None, max_length=200)
    contact_role: str | None = Field(default=None, max_length=200)
    attested: bool = False
    note_to_reviewer: str | None = Field(default=None, max_length=2000)

    @field_validator("fragrance_name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        return _require_text(value, "The fragrance name")

    @field_validator("perfumers", "accords")
    @classmethod
    def _entries_not_blank(cls, values: list[str]) -> list[str]:
        for value in values:
            _require_text(value, "A list entry")
            if len(value) > MAX_ENTRY_LENGTH:
                msg = "List entries are limited to 200 characters"
                raise ValueError(msg)
        return values

    @field_validator("launch_year")
    @classmethod
    def _plausible_year(cls, value: int | None) -> int | None:
        latest = datetime.now(UTC).year + LAUNCH_YEAR_LEAD
        if value is not None and not EARLIEST_LAUNCH_YEAR <= value <= latest:
            msg = f"Launch year must be between {EARLIEST_LAUNCH_YEAR} and {latest}"
            raise ValueError(msg)
        return value

    @field_validator("product_url")
    @classmethod
    def _https_url(cls, value: str | None) -> str | None:
        # #CRITICAL: security: this URL is rendered as a link to managers.
        # Accepting any scheme would let a submission plant a javascript: or
        # data: URL in a manager's view.
        # #VERIFY: only https:// with a host is accepted; covered by
        # test_product_url_requires_https.
        if value is None or not value.strip():
            return None
        if not value.startswith("https://") or len(value) <= len("https://"):
            msg = "The product page must be an https:// address"
            raise ValueError(msg)
        if any(character.isspace() for character in value):
            msg = "The product page address cannot contain spaces"
            raise ValueError(msg)
        return value

    @field_validator("gtins")
    @classmethod
    def _valid_gtins(cls, values: list[str]) -> list[str]:
        invalid = [value for value in values if not is_valid_gtin(value)]
        if invalid:
            msg = (
                "Barcodes must be GTIN-8/12/13/14 digits with a valid check digit: "
                + ", ".join(invalid)
            )
            raise ValueError(msg)
        if len(set(values)) != len(values):
            msg = "Each barcode should be listed once"
            raise ValueError(msg)
        return values

    @model_validator(mode="after")
    def _consistent_notes(self) -> HouseSubmissionPayload:
        # Mirrors uq_fragrance_note_position: the same note may sit in two
        # tiers (musk in heart and base), but not twice in one tier.
        seen: set[tuple[str, str]] = set()
        for note in self.notes:
            key = (note.text, note.position)
            if key in seen:
                msg = f"'{note.text}' is listed twice in the same position"
                raise ValueError(msg)
            seen.add(key)
        if self.note_structure == "linear" and any(
            note.position != "unspecified" for note in self.notes
        ):
            msg = "A note list without a pyramid cannot assign top, heart, or base"
            raise ValueError(msg)
        if self.note_structure == "pyramid" and any(
            note.position == "unspecified" for note in self.notes
        ):
            msg = "Every note in a pyramid needs a top, heart, or base position"
            raise ValueError(msg)
        return self


LabelKind = Literal["note", "accord", "family", "descriptor"]


class DeclaredLabel(BaseModel):
    """One house label in ADR-017's layer-1 ``declared_label`` row shape.

    The table itself is built in D1. Adoption stores these rows in the
    evidence payload now, so D1 copies them rather than re-parsing a house's
    words, and the mapping from the house form is defined (and tested) once.
    """

    label_kind: LabelKind
    raw_text: str
    position: NotePosition
    source_order: int | None


def declared_labels(payload: HouseSubmissionPayload) -> list[DeclaredLabel]:
    """Express a submission's olfactory words as layer-1 rows.

    ``source_order`` is the house's order within one (kind, position) group:
    for notes, the rank within the tier, which is the order R6's
    ``FragranceNote.rank`` will hold once the words are mapped. A family has
    no order. The free-text description is prose, not a label, and stays in
    the payload as written.

    Args:
        payload (HouseSubmissionPayload): Validated submission content.

    Returns:
        list[DeclaredLabel]: Notes, then accords, then the family, verbatim.
    """
    labels: list[DeclaredLabel] = []
    tier_counts: dict[str, int] = {}
    for note in payload.notes:
        order = tier_counts.get(note.position, 0)
        tier_counts[note.position] = order + 1
        labels.append(
            DeclaredLabel(
                label_kind="note",
                raw_text=note.text,
                position=note.position,
                source_order=order,
            )
        )
    labels.extend(
        DeclaredLabel(
            label_kind="accord",
            raw_text=accord,
            position="unspecified",
            source_order=order,
        )
        for order, accord in enumerate(payload.accords)
    )
    if payload.family_as_described and payload.family_as_described.strip():
        labels.append(
            DeclaredLabel(
                label_kind="family",
                raw_text=payload.family_as_described,
                position="unspecified",
                source_order=None,
            )
        )
    return labels


class SubmissionProblem(BaseModel):
    """One reason a draft cannot be submitted yet, keyed to the form field."""

    field: str
    message: str


def _identity_problems(payload: HouseSubmissionPayload) -> list[SubmissionProblem]:
    problems: list[SubmissionProblem] = []
    if payload.concentration is None:
        problems.append(
            SubmissionProblem(field="concentration", message="Choose the concentration")
        )
    elif payload.concentration == "OTHER" and not _has_text(
        payload.concentration_other
    ):
        problems.append(
            SubmissionProblem(
                field="concentration_other", message="Name the concentration"
            )
        )
    # #ASSUME: data-integrity: an announced but unreleased fragrance may not
    # have a fixed launch year yet; every other availability state has one.
    if payload.launch_year is None and payload.availability != "upcoming":
        problems.append(
            SubmissionProblem(field="launch_year", message="Enter the launch year")
        )
    if payload.availability is None:
        problems.append(
            SubmissionProblem(
                field="availability",
                message="Choose whether the fragrance is on sale",
            )
        )
    return problems


def _attestation_problems(payload: HouseSubmissionPayload) -> list[SubmissionProblem]:
    required = [
        (
            "permission_scope",
            payload.permission_scope is not None,
            "Choose how we may use this information",
        ),
        ("contact_name", _has_text(payload.contact_name), "Enter your name"),
        (
            "contact_role",
            _has_text(payload.contact_role),
            "Enter your role at the house",
        ),
        (
            "attested",
            payload.attested,
            "Confirm you may provide this on the house's behalf",
        ),
    ]
    return [
        SubmissionProblem(field=field, message=message)
        for field, present, message in required
        if not present
    ]


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def submission_problems(payload: HouseSubmissionPayload) -> list[SubmissionProblem]:
    """List what a draft still needs before the house can submit it.

    Kept separate from field validation so a partial draft still saves. The
    frontend runs the same checks before it calls submit; this is the
    authoritative copy. Problems are returned in form order.

    Args:
        payload (HouseSubmissionPayload): A draft that already passed field
            validation.

    Returns:
        list[SubmissionProblem]: Empty when the draft may be submitted.
    """
    problems = _identity_problems(payload)
    if not (payload.notes or payload.accords or payload.description):
        problems.append(
            SubmissionProblem(
                field="notes",
                message="Describe the scent with at least one note, an accord, or the official description",
            )
        )
    return problems + _attestation_problems(payload)


class HouseAccessResponse(BaseModel):
    """Which intake capabilities the current identity has."""

    username: str
    house: str | None
    manager: bool
    house_account: bool = False


class HouseSubmissionResponse(BaseModel):
    """A stored submission, as the house or a manager sees it."""

    id: str
    house: str
    status: SubmissionStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    submitted_by: str | None
    permission_state: PermissionScope | None
    supersedes_id: str | None
    superseded_by_id: str | None
    payload: HouseSubmissionPayload
    review_status: ReviewStatus | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    # Manager-only: blanked in responses to a house, which has no use for the
    # reviewing manager's account name or internal catalog ids.
    reviewed_by: str | None = None
    fragrance_id: str | None = None
    source_snapshot_id: str | None = None
