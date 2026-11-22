from datetime import date
from typing import Any

from sqlalchemy import delete

from app.ml import get_model
from app.models import Prediction
from app.pipeline.base import Job, JobContext, parse_day
from app.pipeline.registry import register


@register
class ComputePredictionsJob(Job):
    name = "compute_predictions"
    description = "Run the active likelihood model and store today's predictions"
    uses_api = False

    def execute(self, ctx: JobContext, day: date | str | None = None, **_: Any) -> int:
        target = parse_day(day) or ctx.settings.today()
        model = get_model(ctx.settings)
        results = model.predict(ctx.session, ctx.region, target)

        # Replace any earlier run for the same day and model.
        ctx.session.execute(
            delete(Prediction).where(
                Prediction.region_code == ctx.region,
                Prediction.for_date == target,
                Prediction.model_name == model.name,
            )
        )
        ctx.session.add_all(
            Prediction(
                region_code=ctx.region,
                for_date=target,
                species_code=r.species_code,
                likelihood=round(r.likelihood, 7),
                sample_size=r.sample_size,
                model_name=model.name,
            )
            for r in results
        )
        return len(results)
