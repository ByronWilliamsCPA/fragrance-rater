"""Tests for note and accord label normalization (R6; X-01, X-03)."""

from __future__ import annotations

import pytest

from fragrance_rater.utils.labels import (
    NOTE_KEY_MAX_LENGTH,
    normalize_accord_code,
    normalize_note_key,
)


@pytest.mark.parametrize(
    "raw",
    [
        "Oak Moss",
        "oak moss",
        "oakmoss",
        "OAKMOSS",
        " Oak-Moss ",
        "oak_moss",
        "Oak  Moss",
    ],
)
def test_separator_and_case_variants_share_one_note_key(raw: str) -> None:
    assert normalize_note_key(raw) == "oakmoss"


def test_accents_are_stripped() -> None:
    assert normalize_note_key("Néroli") == normalize_note_key("neroli") == "neroli"
    assert normalize_note_key("Crème brûlée") == "cremebrulee"


def test_different_words_stay_different() -> None:
    # Joining synonyms is a curated alias decision, never a side effect of
    # normalization.
    assert normalize_note_key("vanille") != normalize_note_key("vanilla")


def test_label_with_no_letters_or_digits_has_an_empty_key() -> None:
    assert normalize_note_key("  -- ") == ""


def test_key_is_bounded_to_the_column_width() -> None:
    assert len(normalize_note_key("a" * 500)) == NOTE_KEY_MAX_LENGTH


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("Woody", "woody"),
        ("  Fresh   Spicy ", "fresh spicy"),
        ("WHITE FLORAL", "white floral"),
        ("Épicé", "epice"),
        ("   ", ""),
    ],
)
def test_accord_codes_keep_word_breaks(raw: str, code: str) -> None:
    assert normalize_accord_code(raw) == code
