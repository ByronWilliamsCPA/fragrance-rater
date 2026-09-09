"""Configuration settings for Fragrance Rater.

Settings are loaded from environment variables (no prefix, case-insensitive)
so that names match ``.env.example`` and ``docker-compose.yml``
(``DATABASE_URL``, ``LOG_LEVEL``, ``OPENROUTER_API_KEY``, ...).
Pydantic-settings handles the parsing and validation.

# #CRITICAL: external-resources: most field names below are deliberately
# unprefixed to match the existing .env/docker-compose contract, but this
# means any ambient shell env var sharing a field's name is picked up too.
# ``DEBUG`` and ``LOG_LEVEL`` are common enough (other tools export
# ``DEBUG=express:*`` or lowercase ``LOG_LEVEL=debug``) that this has
# crashed Settings() at import time in practice (Major finding 2).
# #VERIFY: `debug` uses a distinct validation_alias so unrelated ambient
# DEBUG values are never read, and `log_level` uppercases its raw string
# before Literal validation so a lowercase ambient value still parses.
"""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the application, loaded from environment variables.

    Attributes:
        model_config: Pydantic-settings model configuration (env prefix,
            case sensitivity, extra field policy, .env file location).
        project_name (str): Name of the application.
        version (str): Application version string.
        debug (bool): Enable debug mode. Read from ``FRAGRANCE_DEBUG``, not
            the bare ``DEBUG`` name, to avoid colliding with ambient shell
            env vars other tools commonly export.
        log_level (Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']): The
            logging level for the application. Case-insensitive.
        json_logs (bool): Flag to enable or disable JSON formatted logs.
        include_timestamp (bool): Flag to include timestamps in logs.
        api_key (str | None): Shared household API key required on the billed,
            LLM-backed ``POST /ratings`` endpoint (sent by callers as the
            ``X-API-Key`` header). Set via ``FRAGRANCE_RATER_API_KEY``; the
            explicit alias keeps that documented name even though this class
            otherwise reads unprefixed env vars. This is a lightweight,
            single-secret scheme appropriate for a personal/family-use
            deployment, not a multi-tenant auth system. When unset, the
            endpoint rejects all requests with 503 rather than silently
            allowing writes; see ``fragrance_rater.middleware.auth``.
        database_url (str): PostgreSQL connection string.
        database_echo (bool): Echo SQL queries to logs.
        api_v1_prefix (str): API version 1 prefix.
        rate_limit_enabled (bool): Enable the ``slowapi``-backed rate limiter
            (see ``fragrance_rater.middleware.rate_limit``), the single
            rate-limiting mechanism for the whole API. Controls whether
            ``DefaultRateLimitMiddleware``, its exception handler, and
            ``app.state.limiter`` are registered in ``fragrance_rater.main``.
            Defaults to True and is left at that default in the test suite
            (see ``tests/conftest.py``), since the suite exercises the real
            slowapi wiring rather than disabling it; set
            ``RATE_LIMIT_ENABLED=false`` to disable outside tests.
        rate_limit_rpm (int): Allowed requests per minute per client, used to
            build the limiter's ``DEFAULT_RATE_LIMIT``. Does not affect the
            deliberately tighter, hardcoded ``RATINGS_RATE_LIMIT`` on the
            billed ``POST /ratings`` endpoint.
        openrouter_api_key (str): OpenRouter API key for LLM integration.
        openrouter_model (str): Default model to use for LLM calls.
        openrouter_base_url (str): OpenRouter API base URL.
        llm_enabled (bool): Enable/disable LLM features.
        authentik_required (bool): Require a verified Authentik forward-auth
            identity header on mutating requests. Defaults to True outside
            tests; tests and local dev disable it via AUTHENTIK_REQUIRED=false.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Application
    project_name: str = "Fragrance Rater"
    version: str = "0.1.0"
    debug: bool = Field(
        default=False,
        validation_alias="FRAGRANCE_DEBUG",
        description=(
            "Enable debug mode. Intentionally not read from the bare DEBUG "
            "name to avoid crashing on ambient shell env vars (e.g. "
            "DEBUG=express:* from unrelated tooling)."
        ),
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_logs: bool = False
    include_timestamp: bool = True

    # Shared household API key for POST /ratings (see middleware/auth.py).
    # #CRITICAL: security: this class reads unprefixed env vars, so without an
    # explicit alias this field would silently read a bare ``API_KEY`` and the
    # documented ``FRAGRANCE_RATER_API_KEY`` (.env.example, CI workflow,
    # middleware/auth.py error text) would be ignored, leaving the endpoint
    # failing closed with 503 in every deployment.
    # #VERIFY: alias below matches the name used in .env.example and
    # .github/workflows/postman-api-tests.yml; tests/unit/test_core covers it.
    api_key: str | None = Field(
        default=None,
        validation_alias="FRAGRANCE_RATER_API_KEY",
        description=(
            "Shared household API key required as the X-API-Key header on "
            "POST /ratings. Unset means the endpoint fails closed with 503."
        ),
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        """Uppercase a string LOG_LEVEL before Literal validation.

        Args:
            value (object): Raw value from the environment (or a default).

        Returns:
            object: The uppercased string if `value` was a string, otherwise
                `value` unchanged so Pydantic's own type error still fires.
        """
        # #ASSUME: data-integrity: ambient LOG_LEVEL values are frequently
        # lowercase (e.g. LOG_LEVEL=debug from other tools); normalize case
        # here rather than widening the Literal to accept both cases.
        # #VERIFY: non-string values (already-invalid config) pass through
        # untouched so Pydantic still reports a clear validation error.
        if isinstance(value, str):
            return value.upper()
        return value

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://fragrance_rater:password@localhost:5432/fragrance_rater",
        description="PostgreSQL connection string",
    )
    database_echo: bool = Field(
        default=False,
        description="Echo SQL queries to logs",
    )

    # API
    api_v1_prefix: str = "/api/v1"
    rate_limit_enabled: bool = Field(
        default=True,
        description=(
            "Enable the slowapi-backed rate limiter (the single "
            "rate-limiting mechanism for the API)"
        ),
    )
    rate_limit_rpm: int = Field(
        default=60,
        ge=1,
        description=(
            "Rate limit in requests per minute per client, applied by the "
            "slowapi limiter's DEFAULT_RATE_LIMIT"
        ),
    )

    # LLM / OpenRouter
    openrouter_api_key: str = Field(
        default="",
        description="OpenRouter API key for LLM integration",
    )
    openrouter_model: str = Field(
        default="anthropic/claude-3-haiku",
        description="Default model to use (e.g., anthropic/claude-3-haiku, openai/gpt-4o-mini)",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL",
    )
    llm_enabled: bool = Field(
        default=True,
        description="Enable/disable LLM features",
    )

    # Authentik forward-auth (Critical finding 2)
    # #CRITICAL: security: this app is deployed behind Authentik/Traefik
    # forward-auth; when True, mutating requests that lack a verified
    # X-Authentik-Username header (meaning the request bypassed the proxy)
    # are rejected rather than silently treated as anonymous.
    # #VERIFY: default True in production; tests and local dev set
    # AUTHENTIK_REQUIRED=false via an env var set in tests/conftest.py before
    # Settings() is instantiated (rate_limit_enabled is a separate,
    # test-only-disableable toggle but is left at its True default in tests;
    # see the comment above os.environ["AUTHENTIK_REQUIRED"] in conftest.py).
    authentik_required: bool = Field(
        default=True,
        description=(
            "Require a verified Authentik forward-auth identity header on "
            "mutating fragrances/evaluations/reviewers requests."
        ),
    )


# A single, global instance of the settings
settings = Settings()
