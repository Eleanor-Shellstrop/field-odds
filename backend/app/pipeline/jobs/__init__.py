"""Importing this package registers every job with the registry."""

from app.pipeline.jobs import ebird_jobs, predictions

__all__ = ["ebird_jobs", "predictions"]
