"""Sunrise, worked out locally with NOAA's approximation, so no location leaves the machine."""

import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def sunrise(day: date, lat: float, lng: float, zone: ZoneInfo) -> datetime | None:
    """Local sunrise as a naive datetime, or None where the sun doesn't rise or never sets."""
    g = 2 * math.pi / 365 * (day.timetuple().tm_yday - 0.5)
    equation_of_time = 229.18 * (
        0.000075
        + 0.001868 * math.cos(g)
        - 0.032077 * math.sin(g)
        - 0.014615 * math.cos(2 * g)
        - 0.040849 * math.sin(2 * g)
    )
    declination = (
        0.006918
        - 0.399912 * math.cos(g)
        + 0.070257 * math.sin(g)
        - 0.006758 * math.cos(2 * g)
        + 0.000907 * math.sin(2 * g)
        - 0.002697 * math.cos(3 * g)
        + 0.00148 * math.sin(3 * g)
    )
    phi = math.radians(lat)
    cos_hour_angle = math.cos(math.radians(90.833)) / (
        math.cos(phi) * math.cos(declination)
    ) - math.tan(phi) * math.tan(declination)
    if not -1 <= cos_hour_angle <= 1:
        return None

    utc_minutes = 720 - 4 * (lng + math.degrees(math.acos(cos_hour_angle))) - equation_of_time
    midnight_utc = datetime.combine(day, time(), ZoneInfo("UTC"))
    local = (midnight_utc + timedelta(minutes=utc_minutes)).astimezone(zone)
    return local.replace(tzinfo=None)
