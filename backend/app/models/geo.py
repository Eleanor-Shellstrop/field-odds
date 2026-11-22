"""Where observations happened, and the area names that may be shown for private places."""

from sqlalchemy import Float, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Location(Base):
    """An eBird location. Private unless eBird has said otherwise."""

    __tablename__ = "locations"

    loc_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    is_private: Mapped[bool] = mapped_column(default=True, server_default=true())
    lat: Mapped[float | None]
    lng: Mapped[float | None]
    area_name: Mapped[str | None] = mapped_column(String(200))  # only set for private locations


class Boundary(Base):
    """A named polygon used to label private locations. Lowest priority number wins."""

    __tablename__ = "boundaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    priority: Mapped[int]
    name: Mapped[str] = mapped_column(String(200))
    area_km2: Mapped[float] = mapped_column(Float)
    wkt: Mapped[str] = mapped_column(Text)  # longitude/latitude
