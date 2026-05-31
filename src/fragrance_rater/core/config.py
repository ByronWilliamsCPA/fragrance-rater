"""Configuration settings for Fragrance Rater.

Settings are loaded from environment variables with the prefix 'FRAGRANCE_RATER_'.
Pydantic-settings handles the parsing and validation.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the application, loaded from environment variables.

    Attributes:
        model_config (SettingsConfigDict): Pydantic-settings model configuration
            (env prefix, case sensitivity, extra field policy).
        log_level (Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']): The
            logging level for the application.
        json_logs (bool): Flag to enable or disable JSON formatted logs.
        include_timestamp (bool): Flag to include timestamps in logs.
    """

    model_config: SettingsConfigDict = SettingsConfigDict(
        env_prefix="fragrance_rater_",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_logs: bool = False
    include_timestamp: bool = True


# A single, global instance of the settings
settings = Settings()
