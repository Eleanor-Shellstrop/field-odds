from app.config import Settings
from app.ml.base import LikelihoodModel, SpeciesLikelihood
from app.ml.frequency import FrequencyModel


def get_model(settings: Settings) -> LikelihoodModel:
    """Single place to choose the active model."""
    return FrequencyModel(
        years=settings.model_years,
        window_days=settings.model_window_days,
        recent_days=settings.model_recent_days,
        recent_weight=settings.model_recent_weight,
    )


__all__ = ["FrequencyModel", "LikelihoodModel", "SpeciesLikelihood", "get_model"]
