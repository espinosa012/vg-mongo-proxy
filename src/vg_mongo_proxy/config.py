from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mongodb_uri: str = "mongodb://localhost:27017"
    default_database: str = "tasks_db"
    proxy_api_key: str = "dev-secret-key"
    cors_origins: str = "*"

    @property
    def cors_origins_list(self) -> List[str]:
        """Return parsed list of CORS origins."""
        if not self.cors_origins or self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
