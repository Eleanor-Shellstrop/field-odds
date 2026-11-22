"""Give each private location the name of an area that contains it.

Containing, never nearest: the nearest named spot can be many km away (wrong) or a few
hundred metres away (which points at someone's house).
"""

from collections.abc import Iterable

from shapely import from_wkt
from shapely.geometry import Point
from shapely.strtree import STRtree
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Boundary, Location

# An area smaller than this narrows a sighting down to a few streets, so it isn't named.
MIN_AREA_KM2 = 5.0


class AreaLookup:
    def __init__(self, boundaries: list[Boundary]) -> None:
        self._boundaries = boundaries
        self._shapes = [from_wkt(b.wkt) for b in boundaries]
        self._tree = STRtree(self._shapes) if boundaries else None

    def name_for(self, lat: float | None, lng: float | None) -> str | None:
        if self._tree is None or lat is None or lng is None:
            return None
        point = Point(lng, lat)
        inside = [
            self._boundaries[i] for i in self._tree.query(point) if self._shapes[i].covers(point)
        ]
        if not inside:
            return None
        best = min(inside, key=lambda b: (b.priority, b.area_km2))
        # Don't fall through to a bigger area here: a tiny city is also its own subdivision.
        return best.name if best.area_km2 >= MIN_AREA_KM2 else None


def label_locations(session: Session, locations: Iterable[Location]) -> None:
    lookup: AreaLookup | None = None
    for location in locations:
        if not location.is_private:
            location.area_name = None
            continue
        if lookup is None:  # loading the polygons is the slow part, so only when needed
            lookup = AreaLookup(list(session.scalars(select(Boundary))))
        location.area_name = lookup.name_for(location.lat, location.lng)
