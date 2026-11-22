"""Rarity reports from eBird's notable feed, and the private log of searches for them."""

from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class NotableReport(Base):
    """One notable taxon on one checklist. Observer names are never stored."""

    __tablename__ = "notable_reports"
    __table_args__ = (Index("ix_notable_region_dt", "region_code", "obs_dt"),)

    region_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    sub_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    species_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    common_name: Mapped[str] = mapped_column(String(200))
    obs_dt: Mapped[datetime]  # local time, as eBird sends it
    loc_id: Mapped[str | None] = mapped_column(String(20))
    lat: Mapped[float | None]
    lng: Mapped[float | None]
    is_valid: Mapped[bool]
    is_reviewed: Mapped[bool]
    first_captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Set when a report drops out of the feed (usually rejected or deleted), cleared if it returns
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RaritySearch(Base):
    """'I looked: found it / didn't find it.' Deliberately has no location."""

    __tablename__ = "rarity_searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    region_code: Mapped[str] = mapped_column(String(20))
    species_code: Mapped[str] = mapped_column(String(20))
    common_name: Mapped[str] = mapped_column(String(200))
    searched_at: Mapped[datetime]  # local time
    found: Mapped[bool]
    # What the app would have said then, using only what it had captured by then
    status_then: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
