"""Tests for the R7b capture fields on ``ResponseInput``.

Each validator mirrors a database CHECK from migrations ``3f14014a49cb`` and
``cd1e2375a2e4``, so a malformed request is a clear 422 and never a 500 from a
constraint violation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import get_args

import pytest
from pydantic import ValidationError

from fragrance_rater.models.calibration import (
    OWNED_OR_WORN_CODES,
    RECOGNITION_CODES,
    RESPONSE_STATUSES,
    SEASON_FIT_CODES,
    SETTING_FIT_CODES,
)
from fragrance_rater.schemas.calibration import (
    OwnedOrWorn,
    Recognition,
    ResponseInput,
    ResponseStatus,
    SeasonFit,
    SettingFit,
    to_naive_utc,
)


def _skin(**fields: object) -> ResponseInput:
    return ResponseInput(stage="SKIN", **fields)  # type: ignore[arg-type]


def _blotter(**fields: object) -> ResponseInput:
    return ResponseInput(stage="BLOTTER", **fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("literal", "codes"),
    [
        (ResponseStatus, RESPONSE_STATUSES),
        (Recognition, RECOGNITION_CODES),
        (OwnedOrWorn, OWNED_OR_WORN_CODES),
        (SeasonFit, SEASON_FIT_CODES),
        (SettingFit, SETTING_FIT_CODES),
    ],
)
def test_input_vocabularies_match_the_stored_codes(
    literal: object, codes: tuple[str, ...]
) -> None:
    """The API accepts exactly the codes the database CHECKs accept."""
    assert set(get_args(literal)) == set(codes)


def test_a_plain_response_still_validates_and_leaves_r7b_fields_null() -> None:
    response = _blotter(detected=True, intensity=3, liking=7)

    for field in (
        "observed_at",
        "response_status",
        "recognition",
        "owned_or_worn",
        "scrubbed_off",
        "time_to_scrub_minutes",
        "last_detected_elapsed_min",
        "first_not_detected_elapsed_min",
        "season_fit",
        "setting_fit",
    ):
        assert getattr(response, field) is None, field


def test_would_buy_is_still_accepted() -> None:
    """Owner decision 2026-10-30: blind would_buy stays on the form."""
    assert _skin(would_buy=7).would_buy == 7


@pytest.mark.parametrize("code", RECOGNITION_CODES)
def test_every_recognition_code_is_accepted(code: str) -> None:
    assert _blotter(recognition=code).recognition == code


@pytest.mark.parametrize(
    "fields",
    [
        {"recognition": "familiar"},
        {"owned_or_worn": "maybe"},
        {"response_status": "technical_failure"},
        {"season_fit": ["monsoon"], "stage": "SKIN"},
        {"setting_fit": ["beach"], "stage": "SKIN"},
    ],
)
def test_unknown_codes_are_refused(fields: dict[str, object]) -> None:
    fields.setdefault("stage", "BLOTTER")
    with pytest.raises(ValidationError):
        ResponseInput(**fields)  # type: ignore[arg-type]


def test_not_detected_needs_detected_false() -> None:
    ok = _blotter(response_status="not_detected", detected=False, intensity=0)
    assert ok.response_status == "not_detected"

    for detected in (True, None):
        with pytest.raises(ValidationError, match="not_detected requires detected"):
            _blotter(response_status="not_detected", detected=detected)


def test_other_statuses_need_no_detection_answer() -> None:
    for status in ("skipped", "unable_to_assess", "interrupted", "invalidated"):
        assert _blotter(response_status=status).response_status == status


class TestScrubOff:
    def test_scrub_off_with_a_time_is_accepted_on_skin(self) -> None:
        response = _skin(scrubbed_off=True, time_to_scrub_minutes=45)

        assert (response.scrubbed_off, response.time_to_scrub_minutes) == (True, 45)

    def test_scrub_off_false_is_a_recorded_answer(self) -> None:
        assert _skin(scrubbed_off=False).scrubbed_off is False

    def test_a_scrub_time_needs_scrub_off_true(self) -> None:
        for scrubbed in (None, False):
            with pytest.raises(ValidationError, match="requires scrubbed_off true"):
                _skin(scrubbed_off=scrubbed, time_to_scrub_minutes=10)

    def test_scrub_off_is_skin_only(self) -> None:
        for value in (True, False):
            with pytest.raises(ValidationError, match="skin wear only"):
                _blotter(scrubbed_off=value)


class TestLongevityInterval:
    def test_an_ordered_interval_is_accepted(self) -> None:
        response = _skin(
            last_detected_elapsed_min=240, first_not_detected_elapsed_min=480
        )

        assert response.first_not_detected_elapsed_min == 480

    @pytest.mark.parametrize("first", [240, 120])
    def test_first_not_detected_must_exceed_last_detected(self, first: int) -> None:
        with pytest.raises(ValidationError, match="must exceed"):
            _skin(last_detected_elapsed_min=240, first_not_detected_elapsed_min=first)

    def test_either_bound_alone_is_accepted(self) -> None:
        assert (
            _skin(last_detected_elapsed_min=240).first_not_detected_elapsed_min is None
        )
        assert (
            _skin(first_not_detected_elapsed_min=480).last_detected_elapsed_min is None
        )

    def test_negative_minutes_are_refused(self) -> None:
        with pytest.raises(ValidationError):
            _skin(last_detected_elapsed_min=-1)


class TestSeasonAndSettingFit:
    def test_several_options_can_be_ticked(self) -> None:
        response = _skin(
            season_fit=["spring", "fall"], setting_fit=["home", "social_outing"]
        )

        assert response.season_fit == ["spring", "fall"]
        assert response.setting_fit == ["home", "social_outing"]

    @pytest.mark.parametrize("field", ["season_fit", "setting_fit"])
    def test_blotter_rows_never_carry_fit(self, field: str) -> None:
        with pytest.raises(ValidationError, match="skin stage only"):
            _blotter(**{field: ["none"]})

    @pytest.mark.parametrize(
        ("field", "choices"),
        [
            ("season_fit", ["spring", "spring"]),
            ("setting_fit", ["home", "home"]),
        ],
    )
    def test_an_option_cannot_be_listed_twice(
        self, field: str, choices: list[str]
    ) -> None:
        with pytest.raises(ValidationError, match="twice"):
            _skin(**{field: choices})

    @pytest.mark.parametrize(
        ("field", "choices"),
        [
            ("season_fit", ["none", "spring"]),
            ("season_fit", ["cannot_judge", "winter"]),
            ("season_fit", ["none", "cannot_judge"]),
            ("setting_fit", ["none", "home"]),
            ("setting_fit", ["cannot_judge", "other"]),
        ],
    )
    def test_none_and_cannot_judge_stand_alone(
        self, field: str, choices: list[str]
    ) -> None:
        with pytest.raises(ValidationError, match="stand alone"):
            _skin(**{field: choices})

    @pytest.mark.parametrize("field", ["season_fit", "setting_fit"])
    @pytest.mark.parametrize("only", ["none", "cannot_judge"])
    def test_none_or_cannot_judge_alone_is_accepted(
        self, field: str, only: str
    ) -> None:
        assert getattr(_skin(**{field: [only]}), field) == [only]

    def test_an_empty_list_is_no_answer(self) -> None:
        """Blotter forms may send empty lists; they carry no choice."""
        assert _blotter(season_fit=[], setting_fit=[]).season_fit == []


class TestObservedAt:
    def test_a_naive_value_is_taken_as_utc(self) -> None:
        stamp = datetime(2026, 10, 30, 12, 0, 0)  # noqa: DTZ001

        assert _skin(observed_at=stamp).observed_at == stamp

    def test_an_aware_value_is_converted_to_naive_utc(self) -> None:
        local = datetime(2026, 10, 30, 8, 0, 0, tzinfo=timezone(timedelta(hours=-6)))

        converted = _skin(observed_at=local).observed_at

        assert converted == datetime(2026, 10, 30, 14, 0, 0)  # noqa: DTZ001
        assert converted is not None
        assert converted.tzinfo is None

    def test_a_small_clock_skew_is_tolerated(self) -> None:
        soon = datetime.now(UTC) + timedelta(minutes=2)

        assert _skin(observed_at=soon).observed_at is not None

    @pytest.mark.parametrize("hours", [1, 24])
    def test_a_future_stamp_is_refused(self, hours: int) -> None:
        future = datetime.now(UTC) + timedelta(hours=hours)

        with pytest.raises(ValidationError, match="future"):
            _skin(observed_at=future)

    def test_to_naive_utc_rejects_the_future_directly(self) -> None:
        with pytest.raises(ValueError, match="future"):
            to_naive_utc(datetime.now(UTC) + timedelta(days=1))
