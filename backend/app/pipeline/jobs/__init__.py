"""Importing this package registers every job with the registry."""

from app.pipeline.jobs import boundaries, ebird_jobs, histogram, predictions

__all__ = ["boundaries", "ebird_jobs", "histogram", "predictions"]
