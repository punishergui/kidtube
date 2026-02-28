import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_database_url() -> str:
    db_path = os.getenv("KIDTUBE_DB_PATH")
    if db_path:
        return f"sqlite:///{db_path}"
    return "sqlite:////data/kidtube.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "KidTube"
    app_version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 2018
    database_url: str = Field(default_factory=_default_database_url, alias="DATABASE_URL")
    log_level: str = "INFO"
    discord_public_key: str | None = Field(default=None, alias="DISCORD_PUBLIC_KEY")
    discord_approval_webhook_url: str | None = Field(
        default=None, alias="DISCORD_APPROVAL_WEBHOOK_URL"
    )
    youtube_api_key: str | None = Field(default=None, alias="YOUTUBE_API_KEY")
    sync_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("KIDTUBE_SYNC_ENABLED", "SYNC_ENABLED"),
    )
    sync_interval_seconds: int = Field(
        default=900,
        validation_alias=AliasChoices("KIDTUBE_SYNC_INTERVAL_SECONDS", "SYNC_INTERVAL_SECONDS"),
    )
    sync_max_videos_per_channel: int = Field(default=15, alias="SYNC_MAX_VIDEOS_PER_CHANNEL")
    http_timeout_seconds: float = Field(default=10.0, alias="HTTP_TIMEOUT_SECONDS")
    # IMPORTANT: override in production with a strong random value.
    secret_key: str = Field(default="dev-only-change-me", alias="SECRET_KEY")

    @property
    def sqlite_path(self) -> Path | None:
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            return Path(self.database_url.removeprefix(prefix))
        return None


settings = Settings()
