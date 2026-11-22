"""Tables holding data pulled from eBird: raw responses, reference data, and observations."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, utcnow


class RawResponse(Base):
    """Every eBird payload, stored untouched so transforms can be replayed later."""

    __tablename__ = "raw_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(200), index=True)
    params: Mapped[dict[str, Any]]
    region_code: Mapped[str | None] = mapped_column(String(20))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload: Mapped[Any] = mapped_column(JSONType)


class Species(Base):
    """eBird taxonomy (reference data). Loaded by `cli seed-taxonomy`."""

    __tablename__ = "species"

    species_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    common_name: Mapped[str] = mapped_column(String(200))
    sci_name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(20))  # species, spuh, slash, hybrid, ...
    taxon_order: Mapped[float | None] = mapped_column(Float)
    family_common_name: Mapped[str | None] = mapped_column(String(200))


class ChecklistFrequency(Base):
    """Share of complete checklists reporting a species, per quarter-month period (0-47)."""

    __tablename__ = "checklist_frequencies"

    region_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    period: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    species_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    frequency: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int]


class Observation(Base):
    """One species reported on one checklist (eBird 'subId')."""

    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("sub_id", "species_code", name="uq_observation_sub_species"),
        Index("ix_observation_region_date", "region_code", "obs_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    region_code: Mapped[str] = mapped_column(String(20))
    species_code: Mapped[str] = mapped_column(String(20), index=True)
    common_name: Mapped[str] = mapped_column(String(200))
    sci_name: Mapped[str] = mapped_column(String(200))
    sub_id: Mapped[str] = mapped_column(String(20))
    obs_date: Mapped[date]
    obs_dt: Mapped[datetime | None]
    how_many: Mapped[int | None] = mapped_column(Integer)
    loc_id: Mapped[str | None] = mapped_column(String(20))
    loc_name: Mapped[str | None] = mapped_column(String(300))
    lat: Mapped[float | None]
    lng: Mapped[float | None]
    source: Mapped[str] = mapped_column(String(20))  # which job wrote it: recent | historic


class DailyStats(Base):
    """Checklist effort for a region on a day.

    Lets the model tell 'not seen' apart from 'no one looked'.
    """

    __tablename__ = "daily_stats"

    region_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    num_checklists: Mapped[int]
    num_contributors: Mapped[int]
    num_species: Mapped[int]
