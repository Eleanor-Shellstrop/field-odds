from dataclasses import asdict
from datetime import UTC, datetime, time

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import RaritiesResponse, RarityOut
from app.config import Settings, get_settings
from app.db import get_session
from app.models import DailyStats, PipelineRun
from app.rarities.service import EFFORT_LAG, list_rarities, local_now

router = APIRouter(prefix="/api/rarities", tags=["rarities"])


@router.get("", response_model=RaritiesResponse)
def rarities(
    session: Session = Depends(get_session), settings: Settings = Depends(get_settings)
) -> RaritiesResponse:
    """Rarity episodes from the last 30 days: evidence and a status, never a location pin."""
    now = local_now(settings)
    updated = session.scalar(
        select(func.max(PipelineRun.finished_at)).where(
            PipelineRun.job_name == "notable_obs", PipelineRun.status == "success"
        )
    )
    if updated and updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)  # SQLite drops tzinfo
    counted = session.scalar(
        select(func.max(DailyStats.day)).where(
            DailyStats.region_code == settings.region_code,
            DailyStats.day <= (datetime.combine(now.date(), time()) - EFFORT_LAG).date(),
        )
    )
    return RaritiesResponse(
        region_code=settings.region_code,
        today=now.date(),
        updated_at=updated,
        counts_through=counted,
        items=[RarityOut(**asdict(r)) for r in list_rarities(session, settings, now)],
    )
