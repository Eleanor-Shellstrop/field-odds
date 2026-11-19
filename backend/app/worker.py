"""Scheduler process: runs the daily pipeline at SCHEDULE_HOURS (local time).

Runs separately from the API so the two can scale and restart independently. Jobs
contain no scheduling code, so this file can later be swapped for Celery beat,
Prefect, or a cloud scheduler (cron to `python -m app.cli run-pipeline`).
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.pipeline import run_pipeline
from app.runtime import job_context

log = logging.getLogger("fieldodds.worker")


def tick() -> None:
    with job_context() as ctx:
        runs = run_pipeline(ctx)
    log.info("Pipeline tick done: %s", ", ".join(f"{r.job_name}={r.status}" for r in runs))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    scheduler = BlockingScheduler(timezone=settings.zone)
    scheduler.add_job(
        tick,
        CronTrigger(hour=settings.schedule_hours, minute=0, timezone=settings.zone),
        id="daily_pipeline",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    log.info(
        "Worker started: region=%s hours=%s tz=%s jobs=%s",
        settings.region_code,
        settings.schedule_hours,
        settings.tz,
        settings.pipeline_jobs,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
