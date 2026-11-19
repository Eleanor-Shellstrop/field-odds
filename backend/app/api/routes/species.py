from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ObservationOut, SpeciesDetail
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Observation, Species

router = APIRouter(prefix="/api/species", tags=["species"])


@router.get("/{species_code}", response_model=SpeciesDetail)
def species_detail(
    species_code: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SpeciesDetail:
    observations = list(
        session.scalars(
            select(Observation)
            .where(
                Observation.species_code == species_code,
                Observation.region_code == settings.region_code,
            )
            .order_by(Observation.obs_dt.desc())
            .limit(20)
        )
    )
    taxon = session.get(Species, species_code)
    if taxon is None and not observations:
        raise HTTPException(404, f"Unknown species '{species_code}'")

    return SpeciesDetail(
        species_code=species_code,
        common_name=taxon.common_name if taxon else observations[0].common_name,
        sci_name=taxon.sci_name if taxon else observations[0].sci_name,
        family_common_name=taxon.family_common_name if taxon else None,
        recent_observations=[ObservationOut.model_validate(o) for o in observations],
    )
