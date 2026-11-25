"""Window, ordering and ceiling helpers for transcribed paper times (F1)."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import HTTPException

from fragrance_rater.services.transcription_timing import (
    SPRAY_TO_SMELL_CEILING,
    TRANSCRIPTION_WINDOW,
    check_instant,
    seconds_over_ceiling,
    whole_minutes_between,
)
from fragrance_rater.utils.timestamps import now_naive_utc


def _session(created_at: datetime) -> Any:
    return cast("Any", SimpleNamespace(created_at=created_at))


def test_an_instant_inside_the_window_is_accepted() -> None:
    now = now_naive_utc()

    check_instant(now - timedelta(minutes=1), _session(now - timedelta(hours=1)), "x")


def test_an_instant_before_the_session_existed_is_refused() -> None:
    now = now_naive_utc()

    with pytest.raises(HTTPException) as caught:
        check_instant(now - timedelta(hours=2), _session(now - timedelta(hours=1)), "T")

    assert caught.value.status_code == 422
    assert "before this session existed" in str(caught.value.detail)


def test_an_instant_older_than_the_window_is_refused() -> None:
    now = now_naive_utc()
    long_ago = now - TRANSCRIPTION_WINDOW - timedelta(hours=1)

    with pytest.raises(HTTPException, match="days ago"):
        check_instant(long_ago, _session(long_ago - timedelta(days=1)), "T")


def test_the_ceiling_boundary_is_not_a_breach() -> None:
    start = now_naive_utc() - timedelta(hours=1)

    assert seconds_over_ceiling(start, start + SPRAY_TO_SMELL_CEILING) == 0
    assert seconds_over_ceiling(start, start + timedelta(seconds=119)) == 0
    assert (
        seconds_over_ceiling(
            start, start + SPRAY_TO_SMELL_CEILING + timedelta(seconds=1)
        )
        == 1
    )
    assert seconds_over_ceiling(start, start + timedelta(minutes=5)) == 180


def test_whole_minutes_floor() -> None:
    start = now_naive_utc() - timedelta(hours=1)

    assert whole_minutes_between(start, start + timedelta(seconds=119)) == 1
    assert whole_minutes_between(start, start + timedelta(minutes=12)) == 12
