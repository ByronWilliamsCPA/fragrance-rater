"""Consent text loading: the draft guard depends on it parsing correctly (R7b)."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

from fragrance_rater.services.consent import ConsentText, load_consent_text

if TYPE_CHECKING:
    from pathlib import Path


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "consent.md"
    path.write_text(body, encoding="utf-8")
    load_consent_text.cache_clear()
    return path


def test_version_status_and_digest_come_from_the_file(tmp_path: Path) -> None:
    body = "Version: v9\nStatus: approved\n\n# Text\n"
    path = _write(tmp_path, body)

    text = load_consent_text(path)

    assert text.version == "v9"
    assert text.status == "APPROVED"
    assert text.approved is True
    assert text.sha256 == hashlib.sha256(body.encode()).hexdigest()
    assert text.body == body


@pytest.mark.parametrize("status", ["DRAFT", "draft", "PENDING", "approved-ish", ""])
def test_anything_but_approved_is_not_approved(tmp_path: Path, status: str) -> None:
    path = _write(tmp_path, f"Version: v1\nStatus: {status or 'DRAFT'}\n")

    assert load_consent_text(path).approved is False


def test_a_one_byte_change_changes_the_digest(tmp_path: Path) -> None:
    first = load_consent_text(_write(tmp_path, "Version: v1\nStatus: APPROVED\nA\n"))
    second = load_consent_text(_write(tmp_path, "Version: v1\nStatus: APPROVED\nB\n"))

    assert first.sha256 != second.sha256


@pytest.mark.parametrize(
    "body", ["Status: APPROVED\n", "Version: v1\n", "# Just a heading\n", ""]
)
def test_a_text_without_both_headers_is_refused(tmp_path: Path, body: str) -> None:
    path = _write(tmp_path, body)

    with pytest.raises(ValueError, match=r"Version.*Status"):
        load_consent_text(path)


def test_only_an_exact_approved_status_counts() -> None:
    assert ConsentText("v", "APPROVED", "0" * 64, "").approved is True
    assert ConsentText("v", "DRAFT", "0" * 64, "").approved is False
    assert ConsentText("v", "APPROVED ", "0" * 64, "").approved is False
