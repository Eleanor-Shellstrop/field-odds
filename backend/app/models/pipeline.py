"""Tables written by the pipeline itself: run history and model output."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_name: Mapped[str] = mapped_column(String(100), index=True)
    params: Mapped[dict[str, Any]]
    status: Mapped[str] = mapped_column(String(20))  # running | success | failed
    rows_written: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "region_code", "for_date", "species_code", "model_name", name="uq_prediction"
        ),
        Index("ix_prediction_lookup", "region_code", "for_date", "model_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    region_code: Mapped[str] = mapped_column(String(20))
    for_date: Mapped[date]
    species_code: Mapped[str] = mapped_column(String(20))
    likelihood: Mapped[float] = mapped_column(Float)
    model_name: Mapped[str] = mapped_column(String(50))
    sample_size: Mapped[int | None]  # checklists behind the number, where the model knows
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
