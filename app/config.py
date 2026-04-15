from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Main app settings declaration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(description="Async DB connection string.")
    APP_TITLE: str = Field(default="DEMO API")
    MAX_PROMPT_LENGTH: int = Field(default=5000, ge=1)
    API_KEY_HEADER_NAME: str = Field(default="X-API-Key")
    CORS_ALLOW_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    LLM_MODE: Literal["mock", "real"] = Field(
        default="mock",
        description="LLM mode: 'mock' for MockLLM, 'real' for external provider.",
    )
    LLM_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for external LLM provider (required when LLM_MODE=real).",
    )
    LLM_MODEL: str = Field(
        default="google/gemma-3-1b-it:free",
        description="Model name for external LLM provider.",
    )
    LLM_BASE_URL: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for external LLM provider.",
    )


@lru_cache
def get_settings() -> Settings:
    """Returns app settings instance."""
    return Settings()
