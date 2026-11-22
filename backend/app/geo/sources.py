"""Build boundaries from Census files and from groups of eBird hotspots."""

import math
from dataclasses import dataclass
from pathlib import Path

import shapefile
from shapely.affinity import scale
from shapely.geometry import MultiPoint, shape

KM_PER_DEGREE = 111.32
HOTSPOT_BUFFER_KM = 1.0

# Lower wins: a named birding area, then a city or community, then the township around it.
HOTSPOT_AREA, PLACE, SUBDIVISION = 0, 1, 2

# Census legal/statistical area description codes
_TOWNSHIP, _UNORGANIZED = "44", "46"


@dataclass(frozen=True)
class NamedArea:
    priority: int
    name: str
    area_km2: float
    wkt: str


def display_name(name: str, full_name: str, lsad: str) -> str:
    if lsad == _TOWNSHIP:
        return f"{name} Township"
    if lsad == _UNORGANIZED:
        return f"{name} unorganized territory"
    if lsad in ("25", "57"):  # city, census designated place
        return name
    return full_name


def read_census(path: Path, priority: int) -> list[NamedArea]:
    with shapefile.Reader(str(path)) as reader:
        areas = []
        for item in reader.iterShapeRecords():
            record = item.record.as_dict()
            areas.append(
                NamedArea(
                    priority=priority,
                    name=display_name(record["NAME"], record["NAMELSAD"], record["LSAD"]),
                    area_km2=(record["ALAND"] + record["AWATER"]) / 1e6,
                    wkt=shape(item.shape.__geo_interface__).wkt,
                )
            )
    return areas


def hotspot_area(name: str, points: list[tuple[float, float]]) -> NamedArea:
    """Approximate an area with no official boundary: the outline of its hotspots, plus 1 km.

    Only pass public hotspots, or the outline itself would reveal private locations.
    """
    if len(set(points)) < 3:
        raise ValueError(f"Need at least 3 public hotspots starting '{name}' to outline it")
    middle = sum(lat for _, lat in points) / len(points)
    x, y = KM_PER_DEGREE * math.cos(math.radians(middle)), KM_PER_DEGREE
    in_km = scale(MultiPoint(points), x, y, origin=(0, 0))
    outline = in_km.convex_hull.buffer(HOTSPOT_BUFFER_KM)
    return NamedArea(
        priority=HOTSPOT_AREA,
        name=f"{name} area",
        area_km2=outline.area,
        wkt=scale(outline, 1 / x, 1 / y, origin=(0, 0)).wkt,
    )
