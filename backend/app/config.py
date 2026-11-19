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
    # Minimum seconds between eBird requests; keeps backfills polite.
    ebird_min_interval: float = 0.5

    region_code: str = "US-WA-033"
    tz: str = "America/Los_Angeles"
    database_url: str = "sqlite:///./fieldodds.db"

    # Pipeline: which jobs run on each scheduled tick, in order.
    schedule_hours: str = "6,18"
    pipeline_jobs: list[str] = Field(
        default=["recent_obs", "historic_day", "daily_stats", "compute_predictions"]
    )

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
