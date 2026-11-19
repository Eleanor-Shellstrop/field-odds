from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PredictionItem(_Out):
    species_code: str
    common_name: str
    sci_name: str | None
    likelihood: float
    last_seen: date | None
    last_location: str | None


class TodayResponse(_Out):
    region_code: str
    for_date: date | None  # newest prediction date on or before today
    model_name: str
    items: list[PredictionItem]


class ObservationOut(_Out):
    obs_date: date
    obs_dt: datetime | None
    how_many: int | None
    loc_id: str | None
    loc_name: str | None
    lat: float | None
    lng: float | None


class SpeciesDetail(_Out):
    species_code: str
    common_name: str
    sci_name: str
    family_common_name: str | None
    recent_observations: list[ObservationOut]


class PipelineRunOut(_Out):
    id: int
    job_name: str
    params: dict[str, Any]
    status: str
    rows_written: int
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class JobOut(BaseModel):
    name: str
    description: str
