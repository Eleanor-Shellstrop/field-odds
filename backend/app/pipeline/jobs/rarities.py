from datetime import timedelta
from typing import Any

from sqlalchemy import func, select

from app.models import DailyStats, NotableReport
from app.models.base import utcnow
from app.pipeline.base import Job, JobContext
from app.pipeline.registry import register
from app.pipeline.store import store_raw, upsert_locations

BACK_DAYS = 30
EFFORT_AGE_DAYS = 2  # most checklists are submitted within 24-48 hours
MAX_MISSED_DAYS = 7

_OBSERVER_FIELDS = {"userDisplayName", "firstName", "lastName", "userId"}


@register
class NotableObservationsJob(Job):
    name = "notable_obs"
    description = "Rarities, last 30 days (GET /data/obs/{region}/recent/notable)"

    def execute(self, ctx: JobContext, **_: Any) -> int:
        raw, observations = ctx.client.notable_observations(ctx.region, back=BACK_DAYS)
        # simple detail shouldn't include names; this makes sure none are ever archived
        safe = [{k: v for k, v in o.items() if k not in _OBSERVER_FIELDS} for o in raw]
        store_raw(ctx.session, "data/obs/recent/notable", safe, ctx.region, {"back": BACK_DAYS})

        captured_at = utcnow()
        # A day inside the API's window, so reports merely ageing out aren't marked withdrawn
        window_start = ctx.settings.today() - timedelta(days=BACK_DAYS - 1)
        existing = {
            (r.sub_id, r.species_code): r
            for r in ctx.session.scalars(
                select(NotableReport).where(NotableReport.region_code == ctx.region)
            )
        }

        seen = set()
        for o in observations:
            key = (o.sub_id, o.species_code)
            report = existing.get(key)
            if report is None:
                report = NotableReport(
                    region_code=ctx.region,
                    sub_id=o.sub_id,
                    species_code=o.species_code,
                    first_captured_at=captured_at,
                )
                ctx.session.add(report)
                existing[key] = report
            seen.add(key)
            report.common_name = o.common_name
            report.obs_dt = o.obs_dt
            report.loc_id = o.loc_id
            report.lat, report.lng = o.lat, o.lng
            report.is_valid, report.is_reviewed = o.is_valid, o.is_reviewed
            report.withdrawn_at = None

        for key, report in existing.items():
            if key not in seen and not report.withdrawn_at and report.obs_dt.date() >= window_start:
                report.withdrawn_at = captured_at

        upsert_locations(ctx.session, observations)
        return len(observations)


@register
class ChecklistEffortJob(Job):
    name = "checklist_effort"
    description = "County checklist count from two days ago (GET /product/stats)"

    def execute(self, ctx: JobContext, **_: Any) -> int:
        """Normally one call. After days off, one more for each missed day, up to 7."""
        newest = ctx.settings.today() - timedelta(days=EFFORT_AGE_DAYS)
        in_region = DailyStats.region_code == ctx.region
        latest = ctx.session.scalar(
            select(func.max(DailyStats.day)).where(in_region, DailyStats.day <= newest)
        )
        if latest == newest:
            return 0
        missed = min((newest - latest).days - 1, MAX_MISSED_DAYS) if latest else 0
        days = [newest - timedelta(days=n) for n in range(missed, -1, -1)]
        for day in days:
            raw, stats = ctx.client.daily_stats(ctx.region, day)
            store_raw(ctx.session, "product/stats", raw, ctx.region, {"day": day.isoformat()})
            ctx.session.merge(
                DailyStats(
                    region_code=ctx.region,
                    day=day,
                    num_checklists=stats.num_checklists,
                    num_contributors=stats.num_contributors,
                    num_species=stats.num_species,
                )
            )
        return len(days)
