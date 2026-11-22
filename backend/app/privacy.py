"""The one place that decides what the API may reveal about a location.

Every endpoint that returns a location must go through `public_location`.
"""

from dataclasses import dataclass

from app.models import Location

PRIVATE = "Private location"


@dataclass(frozen=True)
class PublicLocation:
    loc_id: str | None
    name: str | None
    lat: float | None
    lng: float | None


def public_location(location: Location | None, name: str | None) -> PublicLocation:
    """Hotspots are shown as they are. Anything else, including unknown, is only an area."""
    if location is not None and not location.is_private:
        return PublicLocation(location.loc_id, name, location.lat, location.lng)
    area = location.area_name if location is not None else None
    return PublicLocation(None, f"{PRIVATE} in {area}" if area else PRIVATE, None, None)
