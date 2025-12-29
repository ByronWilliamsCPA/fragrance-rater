"""
Application configuration using Pydantic Settings.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Fragrance Tracker"
    DEBUG: bool = False
    VERSION: str = "0.1.0"

    # Database
    DATABASE_URL: str = "postgresql://fragrance:fragrance_secret@localhost:5432/fragrance_tracker"

    # External APIs
    FRAGELLA_API_KEY: Optional[str] = None
    FRAGELLA_BASE_URL: str = "https://api.fragella.com/api/v1"
    FRAGELLA_MONTHLY_LIMIT: int = 20

    # OpenRouter for LLM-powered recommendations
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_DEFAULT_MODEL: str = "anthropic/claude-3.5-sonnet"

    # Security
    SECRET_KEY: str = "change-me-in-production"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Data paths
    DATA_DIR: str = "/app/data"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
