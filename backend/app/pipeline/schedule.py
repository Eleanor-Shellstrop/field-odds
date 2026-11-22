"""Decide whether today's pull still needs to run.

State comes from pipeline_runs, so restarts, sleep and manual runs are all accounted
for without the worker remembering anything.
"""

import logging
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select

from app.models import PipelineRun
from app.pipeline.base import JobContext, run_job
from app.pipeline.registry import get_job

log = logging.getLogger(__name__)

MAX_ATTEMPTS_PER_DAY = 3
RETRY_AFTER = timedelta(hours=1)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value  # SQLite drops tzinfo


def run_if_due(ctx: JobContext, now: datetime | None = None) -> list[PipelineRun]:
    """Run each configured job that hasn't succeeded since today's scheduled time.

    Safe to call as often as you like. A failing job gets a few spaced-out attempts
    per day, so an outage or a bad key can't turn into a stream of requests.
    """
    settings = ctx.settings
    now = now or datetime.now(UTC)
    local_now = now.astimezone(settings.zone)
    scheduled = datetime.combine(local_now.date(), time(settings.schedule_hour), settings.zone)
    if local_now < scheduled:
        return []

    runs = []
    for name in settings.pipeline_jobs:
        if get_job(name).uses_api and not settings.ebird_api_key:
            # Not counted as an attempt, so fixing the key and restarting runs right away.
            log.warning("%s skipped: EBIRD_API_KEY is not set", name)
            continue
        attempts = ctx.session.scalars(
            select(PipelineRun).where(
                PipelineRun.job_name == name,
                PipelineRun.started_at >= scheduled.astimezone(UTC),
            )
        ).all()
        if any(a.status == "success" for a in attempts):
            continue
        if len(attempts) >= MAX_ATTEMPTS_PER_DAY:
            continue
        if attempts and now - max(_as_utc(a.started_at) for a in attempts) < RETRY_AFTER:
            continue
        runs.append(run_job(name, ctx))
    return runs
