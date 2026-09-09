"""Tests for Settings environment-variable handling (Major finding 2).

Verifies that Settings() does not crash on common ambient shell env vars
that collide with unprefixed field names, and that log_level accepts
lowercase values before Literal validation.
"""

from __future__ import annotations

import pytest

from fragrance_rater.core.config import Settings


class TestAmbientEnvVarCollisions:
    """Settings() must not crash when common ambient env vars are set."""

    def test_ambient_debug_and_lowercase_log_level_do_not_crash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The exact empirically-observed crash scenario from the review.

        Ambient DEBUG values like ``express:*`` (from unrelated Node
        tooling) are not booleans, and previously caused Settings() to
        raise a validation error at import time because ``debug`` read
        straight from the bare ``DEBUG`` name. Lowercase LOG_LEVEL values
        (e.g. from other tools' conventions) previously failed the
        upper-case-only Literal.
        """
        monkeypatch.setenv("DEBUG", "express:*")
        monkeypatch.setenv("LOG_LEVEL", "debug")

        settings = Settings()

        # `debug` is read from FRAGRANCE_DEBUG, not the ambient DEBUG var,
        # so the non-boolean ambient value is ignored rather than crashing.
        assert settings.debug is False
        # `log_level` is normalized to uppercase before Literal validation.
        assert settings.log_level == "DEBUG"

    def test_fragrance_debug_env_var_is_honored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FRAGRANCE_DEBUG", "true")
        settings = Settings()
        assert settings.debug is True

    def test_log_level_uppercased_from_lowercase_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOG_LEVEL", "warning")
        settings = Settings()
        assert settings.log_level == "WARNING"

    def test_log_level_default_is_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        settings = Settings()
        assert settings.log_level == "INFO"

    def test_invalid_log_level_still_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOG_LEVEL", "not-a-real-level")
        with pytest.raises(ValueError, match="log_level"):
            Settings()
