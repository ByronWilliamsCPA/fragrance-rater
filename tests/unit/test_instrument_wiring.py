"""INSTRUMENT_VERSION reaches both the backend and the frontend build (R7b)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("path", "needle"),
    [
        # The backend records it at activation.
        ("docker-compose.yml", "INSTRUMENT_VERSION: ${INSTRUMENT_VERSION:-}"),
        # The development frontend sees the same value.
        ("docker-compose.yml", "VITE_INSTRUMENT_VERSION=${INSTRUMENT_VERSION:-}"),
        # The production frontend image is built with it.
        ("docker-compose.prod.yml", "VITE_INSTRUMENT_VERSION: ${INSTRUMENT_VERSION:-}"),
        ("frontend/Dockerfile", "ARG VITE_INSTRUMENT_VERSION="),
        ("frontend/Dockerfile", "ENV VITE_INSTRUMENT_VERSION="),
        # Published images are stamped with the commit they were built from.
        (
            ".github/workflows/docker-publish.yml",
            "VITE_INSTRUMENT_VERSION=${{ github.sha }}",
        ),
        # Operators are told to set it.
        (".env.example", "INSTRUMENT_VERSION="),
    ],
)
def test_instrument_version_is_wired(path: str, needle: str) -> None:
    assert needle in _text(path)


def test_the_backend_setting_is_read_from_the_same_variable() -> None:
    assert "INSTRUMENT_VERSION" in _text("src/fragrance_rater/core/config.py")
