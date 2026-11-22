"""The private "I looked" log. One tap, no location."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import SearchIn, SearchOut
from app.config import Settings, get_settings
from app.db import get_session
from app.models import NotableReport, RaritySearch, Species
from app.rarities.episodes import base_name
from app.rarities.service import local_now, status_at

CLOCK_SLACK = timedelta(minutes=5)


def from_this_app(x_field_odds: str | None = Header(None)) -> None:
    # Other websites open in the browser can't add a custom header without passing CORS,
    # so they can't write to the log through localhost.
    if x_field_odds != "1":
        raise HTTPException(403, "Missing X-Field-Odds header")


router = APIRouter(prefix="/api/searches", tags=["searches"], dependencies=[Depends(from_this_app)])


def _bird_name(session: Session, region: str, code: str) -> str | None:
    """Only birds from the notable feed can be logged."""
    names = {
        base_name(name)
        for name in session.scalars(
            select(NotableReport.common_name).where(NotableReport.region_code == region).distinct()
        )
    }
    species = session.get(Species, code)
    if species and species.common_name in names:
        return species.common_name
    form = session.scalar(
        select(NotableReport.common_name)
        .where(NotableReport.region_code == region, NotableReport.species_code == code)
        .limit(1)
    )
    return base_name(form) if form else None


@router.get("", response_model=list[SearchOut])
def list_searches(
    session: Session = Depends(get_session), settings: Settings = Depends(get_settings)
) -> list[RaritySearch]:
    return list(
        session.scalars(
            select(RaritySearch)
            .where(RaritySearch.region_code == settings.region_code)
            .order_by(RaritySearch.searched_at.desc(), RaritySearch.id.desc())
        )
    )


@router.post("", response_model=SearchOut, status_code=201)
def log_search(
    body: SearchIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RaritySearch:
    now = local_now(settings)
    at = body.searched_at or now
    if at.tzinfo:
        at = at.astimezone(settings.zone).replace(tzinfo=None)
    if at > now + CLOCK_SLACK:
        raise HTTPException(422, "A search can't be in the future")
    name = _bird_name(session, settings.region_code, body.species_code)
    if name is None:
        raise HTTPException(404, "That bird isn't in the rarity reports")

    status = status_at(session, settings, body.species_code, at)
    search = RaritySearch(
        region_code=settings.region_code,
        species_code=body.species_code,
        common_name=name,
        searched_at=at,
        found=body.found,
        status_then=status.value if status else None,
    )
    session.add(search)
    session.commit()
    return search


@router.delete("/{search_id}", status_code=204)
def remove_search(
    search_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> None:
    search = session.get(RaritySearch, search_id)
    if search is None or search.region_code != settings.region_code:
        raise HTTPException(404, "No such search")
    session.delete(search)
    session.commit()
