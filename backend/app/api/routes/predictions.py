from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import PredictionItem, TodayResponse
from app.config import Settings, get_settings
from app.db import get_session
from app.ml import get_model
from app.models import Location, Observation, Prediction, Species
from app.privacy import public_location

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


RECENT_DAYS = 7


def _days_ago(seen: date | None, today: date) -> int | None:
    if seen is None:
        return None
    days = (today - seen).days
    return days if 0 <= days <= RECENT_DAYS else None


@router.get("/today", response_model=TodayResponse)
def today(
    region: str | None = None,
    min_likelihood: float = Query(0.0, ge=0, le=1),
    limit: int | None = Query(None, ge=1, le=1000),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TodayResponse:
    """Today's species ranked by likelihood. Falls back to the newest earlier day if
    today's pipeline run hasn't happened yet."""
    region = region or settings.region_code
    model_name = get_model(settings).name

    for_date = session.scalar(
        select(func.max(Prediction.for_date)).where(
            Prediction.region_code == region,
            Prediction.model_name == model_name,
            Prediction.for_date <= settings.today(),
        )
    )
    if for_date is None:
        return TodayResponse(region_code=region, for_date=None, model_name=model_name, items=[])

    # Most recent observation per species, used for "last seen" info.
    ranked = (
        select(
            Observation.species_code,
            Observation.common_name,
            Observation.sci_name,
            Observation.obs_date,
            Observation.loc_id,
            Observation.loc_name,
            func.row_number()
            .over(partition_by=Observation.species_code, order_by=Observation.obs_dt.desc())
            .label("rn"),
        )
        .where(Observation.region_code == region)
        .subquery()
    )
    last = select(ranked).where(ranked.c.rn == 1).subquery()

    stmt = (
        select(
            Prediction.species_code,
            Prediction.likelihood,
            Prediction.sample_size,
            Species.common_name,
            Species.sci_name,
            Species.taxon_order,
            last.c.common_name.label("obs_common_name"),
            last.c.sci_name.label("obs_sci_name"),
            last.c.obs_date,
            last.c.loc_name,
            Location,
        )
        .outerjoin(Species, Species.species_code == Prediction.species_code)
        .outerjoin(last, last.c.species_code == Prediction.species_code)
        .outerjoin(Location, Location.loc_id == last.c.loc_id)
        .where(
            Prediction.region_code == region,
            Prediction.model_name == model_name,
            Prediction.for_date == for_date,
            Prediction.likelihood >= min_likelihood,
        )
        .order_by(Prediction.likelihood.desc(), Species.taxon_order)
        .limit(limit)
    )

    current_day = settings.today()
    items = [
        PredictionItem(
            species_code=r.species_code,
            common_name=r.common_name or r.obs_common_name or r.species_code,
            sci_name=r.sci_name or r.obs_sci_name,
            likelihood=r.likelihood,
            sample_size=r.sample_size,
            reported_days_ago=_days_ago(r.obs_date, current_day),
            last_seen=r.obs_date,
            last_location=public_location(r.Location, r.loc_name).name if r.obs_date else None,
        )
        for r in session.execute(stmt)
    ]
    return TodayResponse(region_code=region, for_date=for_date, model_name=model_name, items=items)
