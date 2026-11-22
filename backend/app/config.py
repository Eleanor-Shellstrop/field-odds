"""Application settings, loaded from environment variables (and a .env file if present)."""

from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    ebird_api_key: str = ""
    ebird_base_url: str = "https://api.ebird.org/v2"
    # Seconds between eBird requests, across all processes. eBird publishes no limit,
    # so stay slower than one per second, and don't allow configuring anything faster.
    ebird_min_interval: float = Field(default=1.1, ge=1.0)

    region_code: str = "US-WA-033"
    tz: str = "America/Los_Angeles"
    database_url: str = "sqlite:///./fieldodds.db"

    # Once a day, at or after this local hour. The default pipeline is one API call.
    # compute_predictions is deliberately absent: recent sightings can't say how many
    # checklists missed a bird, so they must not drive the percentages.
    schedule_hour: int = Field(default=6, ge=0, le=23)
    pipeline_jobs: list[str] = Field(default=["recent_obs"])

    # Likelihood model v1 knobs
    model_years: int = 3
    model_window_days: int = 7
    model_recent_days: int = 14
    model_recent_weight: float = 2.0

    enable_manual_triggers: bool = False
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://localhost:8080"])

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    def today(self) -> date:
        return datetime.now(self.zone).date()


@lru_cache
def get_settings() -> Settings:
    return Settings()
