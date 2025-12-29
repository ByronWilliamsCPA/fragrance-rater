"""Configuration settings for Fragrance Rater.

Settings are loaded from environment variables with the prefix 'FRAGRANCE_RATER_'.
Pydantic-settings handles the parsing and validation.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the application, loaded from environment variables.

    Attributes:
        project_name: Name of the application.
        version: Application version string.
        debug: Enable debug mode.
        log_level: The logging level for the application.
        json_logs: Flag to enable or disable JSON formatted logs.
        include_timestamp: Flag to include timestamps in logs.
        database_url: PostgreSQL connection string.
        database_echo: Echo SQL queries to logs.
        api_v1_prefix: API version 1 prefix.
        openrouter_api_key: OpenRouter API key for LLM integration.
        openrouter_model: Default model to use for LLM calls.
        llm_enabled: Enable/disable LLM features.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    project_name: str = "Fragrance Rater"
    version: str = "0.1.0"
    debug: bool = False

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_logs: bool = False
    include_timestamp: bool = True

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
