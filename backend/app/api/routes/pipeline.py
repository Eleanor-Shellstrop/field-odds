from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import JobOut, PipelineRunOut
from app.config import Settings, get_settings
from app.db import get_session
from app.models import PipelineRun
from app.pipeline import JobContext, run_job
from app.pipeline.registry import all_jobs
from app.runtime import make_ebird_client

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/runs", response_model=list[PipelineRunOut])
def list_runs(
    limit: int = Query(50, ge=1, le=500),
    job: str | None = None,
    session: Session = Depends(get_session),
) -> list[PipelineRun]:
    stmt = select(PipelineRun).order_by(PipelineRun.id.desc()).limit(limit)
    if job:
        stmt = stmt.where(PipelineRun.job_name == job)
    return list(session.scalars(stmt))


@router.get("/jobs", response_model=list[JobOut])
def list_jobs() -> list[JobOut]:
    return [JobOut(name=n, description=j.description) for n, j in sorted(all_jobs().items())]


@router.post("/run/{job_name}", response_model=PipelineRunOut)
def trigger(
    job_name: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PipelineRun:
    """Run a job now (dev convenience). Disabled unless ENABLE_MANUAL_TRIGGERS=true."""
    if not settings.enable_manual_triggers:
        raise HTTPException(403, "Manual triggers are disabled")
    if job_name not in all_jobs():
        raise HTTPException(404, f"Unknown job '{job_name}'")
    ctx = JobContext(
        session=session,
        settings=settings,
        client_factory=lambda: make_ebird_client(settings),
    )
    try:
        return run_job(job_name, ctx)
    finally:
        ctx.close()
