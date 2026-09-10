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


class TestDatabaseUrlDefault:
    """Important finding 3: the built-in DATABASE_URL default must be an

    obvious, non-functional placeholder rather than a plausible real
    credential (e.g. the previous ``password`` literal), so a deployment
    that silently falls back to it fails loudly against any real
    PostgreSQL instance instead of connecting.
    """

    def test_default_is_unmistakably_a_placeholder(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)

        settings = Settings()

        assert "INSECURE-PLACEHOLDER" in settings.database_url
        # Not a plausible real credential like the old "password" literal.
        assert settings.database_url.count("password") == 0

    def test_database_url_env_var_overrides_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://real_user:real_pass@db.internal:5432/prod",
        )

        settings = Settings()

        assert settings.database_url == (
            "postgresql+asyncpg://real_user:real_pass@db.internal:5432/prod"
        )


class TestCorsAllowedOrigins:
    """Important finding 1: `cors_allowed_origins` is the single source of

    truth for the CORS allow-list consumed by `fragrance_rater.main`.
    """

    def test_default_matches_local_docker_compose_origins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

        settings = Settings()

        assert settings.cors_allowed_origins == [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://frontend:3000",
        ]

    def test_comma_separated_env_var_is_split(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "CORS_ALLOWED_ORIGINS",
            "https://app.example.com, https://admin.example.com",
        )

        settings = Settings()

        assert settings.cors_allowed_origins == [
            "https://app.example.com",
            "https://admin.example.com",
        ]

    def test_json_array_env_var_is_parsed_as_json(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://only.example.com"]')

        settings = Settings()

        assert settings.cors_allowed_origins == ["https://only.example.com"]

    def test_empty_string_env_var_yields_empty_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # #EDGE: security: an operator setting CORS_ALLOWED_ORIGINS="" should
        # get a locked-down empty allow-list, not the permissive default.
        # #VERIFY: the comma-split validator filters blank segments, so an
        # empty string yields [] rather than [""].
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "")

        settings = Settings()

        assert settings.cors_allowed_origins == []
