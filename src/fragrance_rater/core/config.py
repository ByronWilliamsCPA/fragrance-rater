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
        database_url (str): PostgreSQL connection string.
        database_echo (bool): Echo SQL queries to logs.
        api_v1_prefix (str): API version 1 prefix.
        rate_limit_enabled (bool): Enable the in-memory rate limiting middleware.
        rate_limit_rpm (int): Allowed requests per minute per client.
        openrouter_api_key (str): OpenRouter API key for LLM integration.
        openrouter_model (str): Default model to use for LLM calls.
        openrouter_base_url (str): OpenRouter API base URL.
        llm_enabled (bool): Enable/disable LLM features.
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
        description="Enable per-client in-memory rate limiting middleware",
    )
    rate_limit_rpm: int = Field(
        default=60,
        ge=1,
        description="Rate limit in requests per minute per client",
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


# A single, global instance of the settings
settings = Settings()
