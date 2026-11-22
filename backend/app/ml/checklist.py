"""Per-checklist frequency: the share of complete checklists that report each species.

Answers "if I go birding at this time of year, how likely am I to record this bird?"
for a typical checklist in the region. It is also the baseline a trained model must beat.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.histogram import period_of
from app.ml.base import SpeciesLikelihood
from app.ml.frequency import EXCLUDED_CATEGORIES
from app.models import ChecklistFrequency as Frequency
from app.models import Species


@dataclass
class ChecklistFrequencyModel:
    name: str = "checklist_frequency_v1"

    def predict(self, session: Session, region: str, target: date) -> list[SpeciesLikelihood]:
        excluded = select(Species.species_code).where(Species.category.in_(EXCLUDED_CATEGORIES))
        rows = session.scalars(
            select(Frequency)
            .where(
                Frequency.region_code == region,
                Frequency.period == period_of(target),
                Frequency.frequency > 0,
                Frequency.sample_size > 0,
                Frequency.species_code.not_in(excluded),
            )
            .order_by(Frequency.frequency.desc(), Frequency.species_code)
        )
        return [SpeciesLikelihood(r.species_code, r.frequency, r.sample_size) for r in rows]
