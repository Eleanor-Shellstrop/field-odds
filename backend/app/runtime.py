"""Wiring shared by the CLI, worker and API: build a JobContext from settings."""

from collections.abc import Iterator
from contextlib import contextmanager

from app.config import Settings, get_settings
from app.db import get_engine, session_factory
from app.ebird import EBirdClient
from app.pipeline import JobContext


def make_ebird_client(settings: Settings) -> EBirdClient:
    return EBirdClient(
        settings.ebird_api_key,
        settings.ebird_base_url,
        settings.ebird_min_interval,
        engine=get_engine(),
    )


@contextmanager
def job_context() -> Iterator[JobContext]:
    settings = get_settings()
    with session_factory()() as session:
        ctx = JobContext(
            session=session,
            settings=settings,
            client_factory=lambda: make_ebird_client(settings),
        )
        try:
            yield ctx
        finally:
            ctx.close()
