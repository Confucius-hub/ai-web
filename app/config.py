from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    "Main app settings declaration."

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(description="Async DB connection string.")

    APP_TITLE: str = Field(default="DEMO API")


def get_settings() -> Settings:
    """
    Returns app settings instance.
    """
    return Settings()
