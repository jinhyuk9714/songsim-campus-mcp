from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SONGSIM_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Songsim Campus Assistant"
    database_path: str = "songsim.db"
    seed_demo_on_start: bool = True
    sync_official_on_start: bool = False
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    kakao_rest_api_key: str | None = None
    official_campus_id: str = "1"
    official_notice_pages: int = 1
    official_course_year: int | None = None
    official_course_semester: int | None = None

    @field_validator("official_course_year", "official_course_semester", mode="before")
    @classmethod
    def blank_course_sync_values_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
