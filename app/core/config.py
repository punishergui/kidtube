import os
from pathlib import Path

from pydantic import Field
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

    @property
    def sqlite_path(self) -> Path | None:
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            return Path(self.database_url.removeprefix(prefix))
        return None


settings = Settings()
