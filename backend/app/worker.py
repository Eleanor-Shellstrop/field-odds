"""Scheduler process: pulls at SCHEDULE_HOUR, and rarities again at RARITY_REFRESH_HOUR.

It checks on startup and every few minutes whether today's pull is still due. A plain
cron trigger would silently miss the run whenever the laptop was asleep or Docker was
stopped. The check itself only reads the database.

Runs separately from the API so the two can scale and restart independently.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.pipeline.schedule import run_if_due
from app.runtime import job_context

log = logging.getLogger("fieldodds.worker")

CHECK_EVERY_MINUTES = 10


def tick() -> None:
    with job_context() as ctx:
        runs = run_if_due(ctx)
    if runs:
        log.info("Daily pull: %s", ", ".join(f"{r.job_name}={r.status}" for r in runs))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("apscheduler").setLevel(logging.WARNING)  # otherwise logs every check
    settings = get_settings()
    scheduler = BlockingScheduler(timezone=settings.zone)
    scheduler.add_job(
        tick,
        IntervalTrigger(minutes=CHECK_EVERY_MINUTES, timezone=settings.zone),
        id="daily_pull",
        next_run_time=datetime.now(settings.zone),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=None,  # after sleep, check late rather than not at all
    )
    log.info(
        "Worker started: region=%s daily_at=%02d:00 rarities_again_at=%02d:00 tz=%s jobs=%s "
        "api_key_set=%s",
        settings.region_code,
        settings.schedule_hour,
        settings.rarity_refresh_hour,
        settings.tz,
        settings.pipeline_jobs,
        bool(settings.ebird_api_key),
    )
    scheduler.start()


if __name__ == "__main__":
    main()
