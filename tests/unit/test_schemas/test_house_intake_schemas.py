"""House intake payload validation and the submit-time completeness check."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from fragrance_rater.schemas.house_intake import (
    EARLIEST_LAUNCH_YEAR,
    HouseSubmissionPayload,
    submission_problems,
)

VALID_GTIN = "3508440005953"


def complete(**overrides: object) -> HouseSubmissionPayload:
    data: dict[str, object] = {
        "fragrance_name": "Bois d'Été",
        "concentration": "EDP",
        "launch_year": 2021,
        "availability": "in_production",
        "notes": [{"text": "Bergamot", "position": "top"}],
        "permission_scope": "retain_and_train",
        "contact_name": "Ana Ruiz",
        "contact_role": "Founder and perfumer",
        "attested": True,
    }
    data.update(overrides)
    return HouseSubmissionPayload.model_validate(data)


def test_complete_payload_has_no_problems():
    assert submission_problems(complete()) == []


def test_house_wording_round_trips_verbatim():
    payload = complete(
        notes=[
            {"text": "Vanille de Madagascar", "position": "base"},
            {"text": "Acqua di Giò accord", "position": "top"},
        ],
        accords=["oud  (aged)"],
        family_as_described="Ambré boisé",
    )
    dumped = payload.model_dump(mode="json")
    assert [note["text"] for note in dumped["notes"]] == [
        "Vanille de Madagascar",
        "Acqua di Giò accord",
    ]
    assert dumped["accords"] == ["oud  (aged)"]
    assert dumped["family_as_described"] == "Ambré boisé"


def test_draft_needs_only_a_name():
    draft = HouseSubmissionPayload(fragrance_name="Working title")
    fields = {problem.field for problem in submission_problems(draft)}
    assert fields == {
        "concentration",
        "launch_year",
        "availability",
        "notes",
        "permission_scope",
        "contact_name",
        "contact_role",
        "attested",
    }


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_rejected(name):
    with pytest.raises(ValidationError):
        HouseSubmissionPayload(fragrance_name=name)


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        HouseSubmissionPayload.model_validate(
            {"fragrance_name": "X", "house": "Someone else"}
        )


def test_other_concentration_needs_a_name():
    fields = {p.field for p in submission_problems(complete(concentration="OTHER"))}
    assert fields == {"concentration_other"}
    named = complete(concentration="OTHER", concentration_other="Eau Fraîche")
    assert submission_problems(named) == []


def test_upcoming_fragrance_may_omit_launch_year():
    assert (
        submission_problems(complete(launch_year=None, availability="upcoming")) == []
    )
    fields = {p.field for p in submission_problems(complete(launch_year=None))}
    assert fields == {"launch_year"}


def test_identity_only_confirmation_needs_some_description():
    fields = {p.field for p in submission_problems(complete(notes=[]))}
    assert fields == {"notes"}
    assert submission_problems(complete(notes=[], accords=["woody"])) == []
    assert submission_problems(complete(notes=[], description="A walk in pines.")) == []


@pytest.mark.parametrize("year", [EARLIEST_LAUNCH_YEAR - 1, datetime.now(UTC).year + 4])
def test_implausible_launch_year_rejected(year):
    with pytest.raises(ValidationError):
        complete(launch_year=year)


@pytest.mark.parametrize(
    "url",
    [
        "http://house.example/perfume",
        "javascript:alert(1)",
        "data:text/html,hi",
        "https://",
        "https://house.example/a b",
    ],
)
def test_product_url_requires_https(url):
    with pytest.raises(ValidationError):
        complete(product_url=url)


def test_https_product_url_accepted_and_blank_cleared():
    assert complete(product_url="https://house.example/p").product_url == (
        "https://house.example/p"
    )
    assert complete(product_url="  ").product_url is None


def test_gtins_validated_and_unique():
    assert complete(gtins=[VALID_GTIN]).gtins == [VALID_GTIN]
    with pytest.raises(ValidationError, match="check digit"):
        complete(gtins=["3508440005954"])
    with pytest.raises(ValidationError, match="once"):
        complete(gtins=[VALID_GTIN, VALID_GTIN])


def test_same_note_in_two_tiers_allowed_but_not_twice_in_one():
    complete(
        notes=[
            {"text": "Musk", "position": "heart"},
            {"text": "Musk", "position": "base"},
        ]
    )
    with pytest.raises(ValidationError, match="twice"):
        complete(
            notes=[
                {"text": "Musk", "position": "base"},
                {"text": "Musk", "position": "base"},
            ]
        )


def test_note_positions_match_structure():
    with pytest.raises(ValidationError, match="pyramid"):
        complete(notes=[{"text": "Iris", "position": "unspecified"}])
    with pytest.raises(ValidationError, match="without a pyramid"):
        complete(note_structure="linear", notes=[{"text": "Iris", "position": "top"}])
    linear = complete(
        note_structure="linear", notes=[{"text": "Iris", "position": "unspecified"}]
    )
    assert submission_problems(linear) == []


@pytest.mark.parametrize("field", ["accords", "perfumers"])
def test_blank_list_entries_rejected(field):
    with pytest.raises(ValidationError):
        complete(**{field: ["  "]})


def test_overlong_list_entry_rejected():
    with pytest.raises(ValidationError):
        complete(accords=["x" * 201])


def test_missing_attestation_and_contact_reported():
    fields = {
        p.field
        for p in submission_problems(
            complete(attested=False, contact_name=" ", contact_role=None)
        )
    }
    assert fields == {"attested", "contact_name", "contact_role"}
