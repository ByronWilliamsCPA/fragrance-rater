"""Configuration settings for Fragrance Rater.

Settings are loaded from environment variables with the prefix 'FRAGRANCE_RATER_'.
Pydantic-settings handles the parsing and validation.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the application, loaded from environment variables.

    Attributes:
        model_config: Pydantic-settings model configuration (env prefix,
            case sensitivity, extra field policy).
        log_level (Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']): The
            logging level for the application.
        json_logs (bool): Flag to enable or disable JSON formatted logs.
        include_timestamp (bool): Flag to include timestamps in logs.
        api_key (str | None): Shared household API key required on mutating
            API endpoints (sent by callers as the ``X-API-Key`` header).
            Set via ``FRAGRANCE_RATER_API_KEY``. This is a lightweight,
            single-secret scheme appropriate for a personal/family-use
            deployment, not a multi-tenant auth system. When unset, mutating
            endpoints reject all requests with 503 rather than silently
            allowing writes; see ``fragrance_rater.middleware.auth``.
    """

    model_config = SettingsConfigDict(
        env_prefix="fragrance_rater_",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_logs: bool = False
    include_timestamp: bool = True
    api_key: str | None = None


# A single, global instance of the settings
settings = Settings()
