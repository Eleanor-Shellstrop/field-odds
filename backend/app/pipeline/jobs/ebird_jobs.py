"""Jobs that pull data from eBird."""

from datetime import date
from typing import Any

from sqlalchemy import delete, insert

from app.models import DailyStats, Species
from app.pipeline.base import Job, JobContext, default_days
from app.pipeline.registry import register
from app.pipeline.store import store_raw, upsert_observations


@register
class RecentObservationsJob(Job):
    name = "recent_obs"
    description = "Latest sighting of each species in the region (GET /data/obs/{region}/recent)"

    def execute(self, ctx: JobContext, back: int | str = 7, **_: Any) -> int:
        back = int(back)
        raw, observations = ctx.client.recent_observations(ctx.region, back=back)
        store_raw(ctx.session, "data/obs/recent", raw, ctx.region, {"back": back})
        return upsert_observations(ctx.session, ctx.region, observations, source="recent")


@register
class HistoricDayJob(Job):
    name = "historic_day"
    description = "All species reported on a date (GET /data/obs/{region}/historic/{y}/{m}/{d})"

    def execute(self, ctx: JobContext, day: date | str | None = None, **_: Any) -> int:
        total = 0
        for d in default_days(ctx, day):
            raw, observations = ctx.client.historic_observations(ctx.region, d)
            store_raw(ctx.session, "data/obs/historic", raw, ctx.region, {"day": d.isoformat()})
            total += upsert_observations(ctx.session, ctx.region, observations, source="historic")
        return total


@register
class DailyStatsJob(Job):
    name = "daily_stats"
    description = "Checklist counts for a date (GET /product/stats/{region}/{y}/{m}/{d})"

    def execute(self, ctx: JobContext, day: date | str | None = None, **_: Any) -> int:
        days = default_days(ctx, day)
        for d in days:
            raw, stats = ctx.client.daily_stats(ctx.region, d)
            store_raw(ctx.session, "product/stats", raw, ctx.region, {"day": d.isoformat()})
            ctx.session.merge(
                DailyStats(
                    region_code=ctx.region,
                    day=d,
                    num_checklists=stats.num_checklists,
                    num_contributors=stats.num_contributors,
                    num_species=stats.num_species,
                )
            )
        return len(days)


@register
class TaxonomyJob(Job):
    name = "taxonomy"
    description = "eBird taxonomy reference data (GET /ref/taxonomy/ebird). Run rarely."

    def execute(self, ctx: JobContext, **_: Any) -> int:
        # The raw taxonomy is large (~17k taxa) and static, so it isn't archived.
        _, taxa = ctx.client.taxonomy()
        rows = [
            {
                "species_code": t.species_code,
                "common_name": t.common_name,
                "sci_name": t.sci_name,
                "category": t.category,
                "taxon_order": t.taxon_order,
                "family_common_name": t.family_common_name,
            }
            for t in taxa
        ]
        # Full refresh: the taxonomy is replaced as a whole once a year.
        ctx.session.execute(delete(Species))
        ctx.session.execute(insert(Species), rows)
        return len(rows)
