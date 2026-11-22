"""Pipeline building blocks.

A Job does one unit of work (usually: call one eBird endpoint, archive the raw payload,
transform it, load it). `run_job` wraps every execution in a PipelineRun row so each
run is observable from the API and the UI.
"""

import logging
import traceback
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, ClassVar

from sqlalchemy.orm import Session

from app.config import Settings
from app.ebird import EBirdClient
from app.models import PipelineRun
from app.models.base import utcnow

log = logging.getLogger(__name__)


@dataclass
class JobContext:
    session: Session
    settings: Settings
    client_factory: Callable[[], EBirdClient]
    _client: EBirdClient | None = field(default=None, init=False)

    @property
    def client(self) -> EBirdClient:
        """Created on first use, so jobs that never call eBird don't need an API key."""
        if self._client is None:
            self._client = self.client_factory()
        return self._client

    @property
    def region(self) -> str:
        return self.settings.region_code

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


class Job(ABC):
    name: ClassVar[str]
    description: ClassVar[str] = ""
    uses_api: ClassVar[bool] = True  # False means it can run without an eBird key

    @abstractmethod
    def execute(self, ctx: JobContext, **params: Any) -> int:
        """Do the work and return the number of rows written. Don't commit; run_job does."""


def parse_day(value: date | str | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)


def default_days(ctx: JobContext, day: date | str | None) -> list[date]:
    """An explicit day, or else yesterday and today.

    Yesterday is fetched again because many checklists are submitted the day after.
    """
    parsed = parse_day(day)
    if parsed:
        return [parsed]
    today = ctx.settings.today()
    return [today - timedelta(days=1), today]


def _jsonable(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v.isoformat() if isinstance(v, date) else v for k, v in params.items()}


def run_job(name: str, ctx: JobContext, **params: Any) -> PipelineRun:
    from app.pipeline.registry import get_job

    job = get_job(name)
    run = PipelineRun(job_name=name, params=_jsonable(params), status="running")
    ctx.session.add(run)
    ctx.session.commit()

    try:
        rows = job.execute(ctx, **params)
        ctx.session.commit()
        run.status, run.rows_written = "success", rows
    except Exception:
        ctx.session.rollback()
        log.exception("Job %s failed", name)
        run.status, run.error = "failed", traceback.format_exc(limit=5)

    run.finished_at = utcnow()
    ctx.session.add(run)
    ctx.session.commit()
    log.info("Job %s finished: %s (%s rows)", name, run.status, run.rows_written)
    return run


def run_pipeline(ctx: JobContext, job_names: list[str] | None = None) -> list[PipelineRun]:
    """Run the configured jobs in order. A failed job is recorded and the rest still run."""
    names = job_names or ctx.settings.pipeline_jobs
    return [run_job(name, ctx) for name in names]
