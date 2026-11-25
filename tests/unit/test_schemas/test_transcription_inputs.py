"""Spray, first-smell and column-finished rules of a transcribed paper column (F1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from fragrance_rater.schemas.calibration import ExposureInput, ResponseInput


def _ago(**delta: float) -> str:
    return (datetime.now(UTC) - timedelta(**delta)).isoformat()


def test_elapsed_minutes_are_computed_from_spray_to_finish() -> None:
    data = ResponseInput(
        stage="BLOTTER",
        sprayed_at=_ago(minutes=20),
        observed_at=_ago(minutes=7, seconds=30),
    )

    assert data.elapsed_minutes == 12


def test_whole_minutes_are_floored_not_rounded() -> None:
    data = ResponseInput(
        stage="BLOTTER", sprayed_at=_ago(minutes=10), observed_at=_ago(seconds=1)
    )

    assert data.elapsed_minutes == 9


def test_a_matching_elapsed_minutes_is_accepted() -> None:
    data = ResponseInput(
        stage="BLOTTER",
        elapsed_minutes=12,
        sprayed_at=_ago(minutes=20),
        observed_at=_ago(minutes=7, seconds=30),
    )

    assert data.elapsed_minutes == 12


def test_a_contradicting_elapsed_minutes_is_refused() -> None:
    with pytest.raises(ValidationError, match="whole minutes"):
        ResponseInput(
            stage="BLOTTER",
            elapsed_minutes=3,
            sprayed_at=_ago(minutes=20),
            observed_at=_ago(minutes=7),
        )


def test_an_explicit_zero_is_checked_not_treated_as_missing() -> None:
    with pytest.raises(ValidationError, match="whole minutes"):
        ResponseInput(
            stage="BLOTTER",
            elapsed_minutes=0,
            sprayed_at=_ago(minutes=20),
            observed_at=_ago(minutes=7),
        )


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"sprayed_at": _ago(minutes=5)}, "needs observed_at"),
        (
            {"sprayed_at": _ago(minutes=5), "observed_at": _ago(minutes=9)},
            "before the blotter was sprayed",
        ),
    ],
)
def test_response_spray_time_needs_a_later_finish(
    fields: dict[str, str], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        ResponseInput(stage="BLOTTER", **fields)


def test_spray_time_is_blotter_only_on_a_response() -> None:
    with pytest.raises(ValidationError, match="blotter column only"):
        ResponseInput(
            stage="SKIN", sprayed_at=_ago(minutes=9), observed_at=_ago(minutes=1)
        )


def test_a_future_spray_time_is_refused() -> None:
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    with pytest.raises(ValidationError, match="future"):
        ResponseInput(stage="BLOTTER", sprayed_at=future)


def test_exposure_spray_time_needs_a_first_smell_time_after_it() -> None:
    with pytest.raises(ValidationError, match="needs at"):
        ExposureInput(stage="BLOTTER", sprayed_at=_ago(minutes=5))
    with pytest.raises(ValidationError, match="before it was sprayed"):
        ExposureInput(stage="BLOTTER", sprayed_at=_ago(minutes=2), at=_ago(minutes=4))
    ok = ExposureInput(stage="BLOTTER", sprayed_at=_ago(minutes=4), at=_ago(minutes=2))
    assert ok.at is not None


def test_exposure_spray_time_is_blotter_only() -> None:
    with pytest.raises(ValidationError, match="blotter exposure only"):
        ExposureInput(stage="SKIN", sprayed_at=_ago(minutes=4), at=_ago(minutes=2))
