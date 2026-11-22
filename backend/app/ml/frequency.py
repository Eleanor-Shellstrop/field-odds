"""Likelihood model v1: seasonal-window detection frequency.

For a target date D the model samples:
  * seasonal days: D ± window_days in each of the previous `years` years
  * recent days:   the `recent_days` days just before D (weighted higher)

A sampled day counts only if someone birded that day (≥1 checklist), so a day with no
effort doesn't count as "not seen". Then:

    likelihood(species) = Σ weight(days species was reported) / Σ weight(effort days)

The result is "the share of comparable days on which someone reported this species".
It's simple, explainable, and a solid baseline for later ML models.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.base import SpeciesLikelihood
from app.models import DailyStats, Observation, Species

# Taxa that aren't a single identifiable species (e.g. "gull sp.", "Mallard x Black Duck").
EXCLUDED_CATEGORIES = {"spuh", "slash", "hybrid", "domestic"}


def _same_day_in_year(d: date, year: int) -> date:
    try:
        return d.replace(year=year)
    except ValueError:  # Feb 29 in a non-leap year
        return d.replace(year=year, day=28)


def sample_days(
    target: date, years: int, window_days: int, recent_days: int, recent_weight: float
) -> dict[date, float]:
    days: dict[date, float] = {}
    for y in range(1, years + 1):
        center = _same_day_in_year(target, target.year - y)
        for offset in range(-window_days, window_days + 1):
            days[center + timedelta(days=offset)] = 1.0
    for offset in range(1, recent_days + 1):
        days[target - timedelta(days=offset)] = recent_weight
    return days


def compute_likelihoods(
    weights: dict[date, float],
    effort_days: set[date],
    detections: dict[str, set[date]],
) -> list[SpeciesLikelihood]:
    """Pure function at the core of the model, so it can be unit tested without a db."""
    counted = {d: w for d, w in weights.items() if d in effort_days}
    total = sum(counted.values())
    if total == 0:
        return []
    results = [
        SpeciesLikelihood(code, sum(counted[d] for d in seen if d in counted) / total)
        for code, seen in detections.items()
    ]
    results = [r for r in results if r.likelihood > 0]
    return sorted(results, key=lambda r: (-r.likelihood, r.species_code))


@dataclass
class FrequencyModel:
    years: int = 3
    window_days: int = 7
    recent_days: int = 14
    recent_weight: float = 2.0
    name: str = "frequency_v1"

    def predict(self, session: Session, region: str, target: date) -> list[SpeciesLikelihood]:
        weights = sample_days(
            target, self.years, self.window_days, self.recent_days, self.recent_weight
        )
        lo, hi = min(weights), max(weights)

        effort_days = set(
            session.scalars(
                select(DailyStats.day).where(
                    DailyStats.region_code == region,
                    DailyStats.day.between(lo, hi),
                    DailyStats.num_checklists > 0,
                )
            )
        )

        excluded = select(Species.species_code).where(Species.category.in_(EXCLUDED_CATEGORIES))
        rows = session.execute(
            select(Observation.species_code, Observation.obs_date)
            .where(
                Observation.region_code == region,
                # The recent feed has only each species' latest sighting, so counting it
                # would make every other species look absent on those days.
                Observation.source == "historic",
                Observation.obs_date.between(lo, hi),
                Observation.species_code.not_in(excluded),
            )
            .distinct()
        )
        detections: dict[str, set[date]] = defaultdict(set)
        for code, day in rows:
            detections[code].add(day)
            # If stats are missing for a day but someone reported a bird, there was effort.
            effort_days.add(day)

        return compute_likelihoods(weights, effort_days, detections)
