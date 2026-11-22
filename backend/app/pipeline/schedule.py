"""Decide which scheduled pulls still need to run.

State comes from pipeline_runs, so restarts, sleep and manual runs are all accounted
for without the worker remembering anything.
"""

import logging
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select

from app.config import Settings
from app.models import PipelineRun
from app.pipeline.base import JobContext, run_job
from app.pipeline.registry import get_job

log = logging.getLogger(__name__)

MAX_ATTEMPTS_PER_SLOT = 3
RETRY_AFTER = timedelta(hours=1)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value  # SQLite drops tzinfo


def scheduled_hours(settings: Settings, job_name: str) -> list[int]:
    hours = {settings.schedule_hour}
    if job_name == "notable_obs":
        hours.add(settings.rarity_refresh_hour)
    return sorted(hours)


def run_if_due(ctx: JobContext, now: datetime | None = None) -> list[PipelineRun]:
    """Run each configured job that hasn't succeeded since its latest scheduled time today.

    Safe to call as often as you like. Missed slots collapse into one run, and a failing
    job gets a few spaced-out attempts per slot, so an outage or a bad key can't turn
    into a stream of requests.
    """
    settings = ctx.settings
    now = now or datetime.now(UTC)
    local_now = now.astimezone(settings.zone)
    runs = []
    for name in settings.pipeline_jobs:
        passed = [h for h in scheduled_hours(settings, name) if h <= local_now.hour]
        if not passed:
            continue
        scheduled = datetime.combine(local_now.date(), time(passed[-1]), settings.zone)
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
        if len(attempts) >= MAX_ATTEMPTS_PER_SLOT:
            continue
        if attempts and now - max(_as_utc(a.started_at) for a in attempts) < RETRY_AFTER:
            continue
        runs.append(run_job(name, ctx))
    return runs
