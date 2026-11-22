"""Load helpers shared by jobs. Writes are idempotent, so re-running a job is always safe."""

from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.ebird.schemas import EBirdObservation
from app.geo.labels import label_locations
from app.models import Location, Observation, RawResponse


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


def _insert_observations(session: Session, source: str) -> Any:
    postgres = session.get_bind().dialect.name == "postgresql"
    stmt = (pg_insert if postgres else sqlite_insert)(Observation)
    key = ["sub_id", "species_code"]
    if source == "historic":
        # The model only reads historic rows, so historic must win over recent.
        return stmt.on_conflict_do_update(index_elements=key, set_={"source": source})
    return stmt.on_conflict_do_nothing(index_elements=key)


def upsert_locations(session: Session, observations: list[EBirdObservation]) -> None:
    latest: dict[str, EBirdObservation] = {}
    for o in observations:
        if not o.loc_id:
            continue
        # If one response disagrees with itself about a location, private wins.
        if o.loc_id not in latest or o.location_private:
            latest[o.loc_id] = o
    locations = [
        session.merge(
            Location(
                loc_id=loc_id,
                is_private=o.location_private,
                lat=o.lat,
                lng=o.lng,
                public_name=None if o.location_private else o.loc_name,
            )
        )
        for loc_id, o in latest.items()
    ]
    label_locations(session, locations)


def upsert_observations(
    session: Session, region: str, observations: list[EBirdObservation], source: str
) -> int:
    """Insert observations once per (sub_id, species).

    If both feeds return the same observation, it is kept as `historic`.
    """
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
    session.execute(_insert_observations(session, source), rows)
    upsert_locations(session, observations)
    return len(rows)
