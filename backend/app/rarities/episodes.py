"""Group notable reports into episodes: one bird (or flock) staying in one area.

A single pin is not where the bird is: people drop pins where they parked or started
walking. The middle of many pins is stable, so grouping works from the median.
"""

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from statistics import median

SAME_AREA_KM = 3.0
STRAY_PIN_KM = 25.0
STRAY_NEEDS_OUTINGS = 5  # only a well-established episode can absorb a stray pin
MAX_GAP = timedelta(days=7)

_FORM = re.compile(r"\s*\([^)]*\)$")


def base_name(common_name: str) -> str:
    """'Red Crossbill (Ponderosa Pine or type 2)' -> 'Red Crossbill'."""
    return _FORM.sub("", common_name)


@dataclass(frozen=True)
class Report:
    sub_id: str
    species_code: str
    common_name: str
    at: datetime
    loc_id: str | None
    lat: float | None
    lng: float | None
    reviewed: bool = True

    @property
    def outing(self) -> tuple[datetime, str]:
        # Shared checklists repeat the same start time and place.
        return (self.at, self.loc_id or self.sub_id)


@dataclass
class Episode:
    name: str
    reports: list[Report] = field(default_factory=list)
    strays: list[Report] = field(default_factory=list)  # counted, but never used to place it

    @property
    def everything(self) -> list[Report]:
        return self.reports + self.strays

    @property
    def first(self) -> datetime:
        return min(r.at for r in self.everything)

    @property
    def last(self) -> datetime:
        return max(r.at for r in self.everything)

    @property
    def center(self) -> tuple[float, float] | None:
        """For grouping and daylight only. Never send this to the browser."""
        lats = [r.lat for r in self.reports if r.lat is not None]
        lngs = [r.lng for r in self.reports if r.lng is not None]
        return (median(lats), median(lngs)) if lats and lngs else None

    @property
    def outings(self) -> int:
        return len({r.outing for r in self.everything})

    def outings_by_day(self) -> Counter[date]:
        return Counter(at.date() for at, _ in {r.outing for r in self.everything})


def km_between(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float:
    if a is None or b is None:
        return math.inf
    x = math.radians(b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
    y = math.radians(b[0] - a[0])
    return 6371 * math.hypot(x, y)


def build_episodes(reports: list[Report]) -> list[Episode]:
    by_bird: defaultdict[str, list[Report]] = defaultdict(list)
    for report in reports:
        by_bird[base_name(report.common_name)].append(report)

    episodes: list[Episode] = []
    for name, group in by_bird.items():
        found: list[Episode] = []
        for report in sorted(group, key=lambda r: (r.at, r.sub_id)):
            here = (
                (report.lat, report.lng)
                if report.lat is not None and report.lng is not None
                else None
            )
            near = [
                (distance, i)
                for i, episode in enumerate(found)
                if report.at - episode.last <= MAX_GAP
                and (distance := km_between(episode.center, here)) <= SAME_AREA_KM
            ]
            if near:
                found[min(near)[1]].reports.append(report)
            else:
                found.append(Episode(name, [report]))
        episodes += _absorb_stray_pins(found)
    return episodes


def _absorb_stray_pins(episodes: list[Episode]) -> list[Episode]:
    established = [e for e in episodes if e.outings >= STRAY_NEEDS_OUTINGS]
    kept: list[Episode] = []
    for episode in episodes:
        hosts = [
            (distance, i)
            for i, host in enumerate(established)
            if episode.outings == 1
            and host.first <= episode.first <= host.last
            and (distance := km_between(host.center, episode.center)) <= STRAY_PIN_KM
        ]
        if hosts:
            established[min(hosts)[1]].strays += episode.reports
        else:
            kept.append(episode)
    return kept
