"""Load helpers shared by jobs. Writes are idempotent, so re-running a job is always safe."""

from typing import Any

from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.ebird.schemas import EBirdObservation
from app.models import Observation, RawResponse


def store_raw(
    session: Session,
    endpoint: str,
    payload: Any,
    region: str | None = None,
    params: dict[str, Any] | None = None,
) -> None:
    session.add(
        RawResponse(endpoint=endpoint, params=params or {}, region_code=region, payload=payload)
    )


def _insert_ignore(session: Session, table: Any) -> Any:
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return pg_insert(table).on_conflict_do_nothing()
    if dialect == "sqlite":
        return sqlite_insert(table).on_conflict_do_nothing()
    return insert(table)


def upsert_observations(
    session: Session, region: str, observations: list[EBirdObservation], source: str
) -> int:
    """Insert observations, skipping any (sub_id, species) pair already stored."""
    if not observations:
        return 0
    rows = [
        {
            "region_code": region,
            "species_code": o.species_code,
            "common_name": o.common_name,
            "sci_name": o.sci_name,
            "sub_id": o.sub_id,
            "obs_date": o.obs_date,
            "obs_dt": o.obs_dt,
            "how_many": o.how_many,
            "loc_id": o.loc_id,
            "loc_name": o.loc_name,
            "lat": o.lat,
            "lng": o.lng,
            "source": source,
        }
        for o in observations
    ]
    session.execute(_insert_ignore(session, Observation), rows)
    return len(rows)
