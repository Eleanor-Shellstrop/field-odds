from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ObservationOut, SpeciesDetail
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Location, Observation, Species
from app.privacy import public_location

router = APIRouter(prefix="/api/species", tags=["species"])


def _observation_out(observation: Observation, location: Location | None) -> ObservationOut:
    shown = public_location(location, observation.loc_name)
    return ObservationOut(
        obs_date=observation.obs_date,
        obs_dt=observation.obs_dt,
        how_many=observation.how_many,
        loc_id=shown.loc_id,
        loc_name=shown.name,
        lat=shown.lat,
        lng=shown.lng,
    )


@router.get("/{species_code}", response_model=SpeciesDetail)
def species_detail(
    species_code: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SpeciesDetail:
    rows = session.execute(
        select(Observation, Location)
        .outerjoin(Location, Location.loc_id == Observation.loc_id)
        .where(
            Observation.species_code == species_code,
            Observation.region_code == settings.region_code,
        )
        .order_by(Observation.obs_dt.desc())
        .limit(20)
    ).all()
    observations = [observation for observation, _ in rows]
    taxon = session.get(Species, species_code)
    if taxon is None and not observations:
        raise HTTPException(404, f"Unknown species '{species_code}'")

    return SpeciesDetail(
        species_code=species_code,
        common_name=taxon.common_name if taxon else observations[0].common_name,
        sci_name=taxon.sci_name if taxon else observations[0].sci_name,
        family_common_name=taxon.family_common_name if taxon else None,
        recent_observations=[_observation_out(o, loc) for o, loc in rows],
    )
