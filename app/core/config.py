"""
Конфигурация приложения на Pydantic Settings.
Все секреты и настройки читаются из переменных окружения (.env).
Никакого хардкода.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_env: str = Field(default="production")
    log_level: str = Field(default="INFO")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@postgres:5432/ai_web_db"
    )

    # --- Redis ---
    redis_url: str = Field(default="redis://redis:6379/0")
    celery_broker_url: str = Field(default="redis://redis:6379/1")
    celery_result_backend: str = Field(default="redis://redis:6379/2")

    # --- LLM ---
    llm_mode: Literal["mock", "real"] = Field(default="mock")
    llm_api_key: str = Field(default="")
    llm_model: str = Field(default="google/gemma-3-1b-it:free")
    llm_base_url: str = Field(default="https://openrouter.ai/api/v1")
    # Управление ресурсами: ограничение max_new_tokens для LLM
    llm_max_new_tokens: int = Field(default=256, ge=16, le=4096)
    llm_timeout_seconds: int = Field(default=30, ge=5, le=300)

    # --- Local ONNX model (intent classifier) ---
    local_model_path: str = Field(default="/app/models/intent_classifier.onnx")
    local_labels_path: str = Field(default="/app/models/labels.json")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton pattern — Settings грузятся один раз."""
    return Settings()
