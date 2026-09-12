"""Tests for calibration input schemas."""

import pytest
from pydantic import ValidationError

from fragrance_rater.schemas.calibration import MembershipInput


def _base_kwargs(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "fragrance_id": "f1",
        "role": "UNIVERSAL_BASELINE",
        "identity_evidence": "Verified exact label",
    }
    kwargs.update(overrides)
    return kwargs


class TestMembershipInputGtin:
    """gtin is optional but, when given, must be a real GS1 GTIN - the
    strongest identity signal this project has (see
    `fragrance_rater.utils.gtin`)."""

    def test_gtin_is_optional(self):
        member = MembershipInput(**_base_kwargs())
        assert member.gtin is None

    def test_accepts_a_valid_gtin(self):
        """Chanel N5 (Parfum)'s real gtin13, per its Parfumo page."""
        member = MembershipInput(**_base_kwargs(gtin="3508440005953"))
        assert member.gtin == "3508440005953"

    def test_rejects_an_invalid_check_digit(self):
        with pytest.raises(ValidationError, match="GS1 check digit"):
            MembershipInput(**_base_kwargs(gtin="3508440005950"))

    def test_rejects_non_digit_gtin(self):
        with pytest.raises(ValidationError):
            MembershipInput(**_base_kwargs(gtin="not-a-barcode"))
