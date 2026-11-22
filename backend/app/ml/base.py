from dataclasses import dataclass
from datetime import date
from typing import Protocol

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class SpeciesLikelihood:
    species_code: str
    likelihood: float  # 0..1
    sample_size: int | None = None


class LikelihoodModel(Protocol):
    """Any model that can say how likely each species is in a region on a date.

    v1 is a weighted frequency count (ml/frequency.py). A trained model (for example
    logistic regression on day-of-year, weather and effort) can implement this same
    interface without changes to the pipeline, API or UI.
    """

    name: str

    def predict(self, session: Session, region: str, target: date) -> list[SpeciesLikelihood]: ...
