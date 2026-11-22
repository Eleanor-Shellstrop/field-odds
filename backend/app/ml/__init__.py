from app.config import Settings
from app.ml.base import LikelihoodModel, SpeciesLikelihood
from app.ml.checklist import ChecklistFrequencyModel
from app.ml.frequency import FrequencyModel


def get_model(settings: Settings) -> LikelihoodModel:
    """Single place to choose the active model."""
    return ChecklistFrequencyModel()


__all__ = [
    "ChecklistFrequencyModel",
    "FrequencyModel",
    "LikelihoodModel",
    "SpeciesLikelihood",
    "get_model",
]
