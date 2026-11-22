"""Turn stored reports into what the API may show. No coordinates or ids leave here."""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import ChecklistFrequency, DailyStats, Location, NotableReport, Species
from app.privacy import public_location
from app.rarities.episodes import Episode, Report, build_episodes
from app.rarities.status import Status, status_of

HISTORY = timedelta(days=30)
CURRENT = timedelta(days=14)
EFFORT_LAG = timedelta(days=2)
# A species on under 0.1% of checklists across the year is rare here, not just out of season.
RARE_MEAN_FREQUENCY = 0.001
MAX_HOTSPOTS = 3


@dataclass(frozen=True)
class Rarity:
    species_code: str
    common_name: str
    status: Status
    reason: str | None
    first_reported: datetime
    last_reported: datetime
    outings: int
    outings_today: int
    outings_yesterday: int
    days_reported: int
    unreviewed: bool
    hotspots: list[str]
    area: str | None
    is_current: bool


def local_now(settings: Settings) -> datetime:
    return datetime.now(settings.zone).replace(tzinfo=None)


def load_reports(
    session: Session, region: str, now: datetime, known_by: datetime | None = None
) -> list[Report]:
    """Valid or awaiting-review reports up to `now`. `known_by` rewinds what had been captured."""
    stmt = select(NotableReport).where(
        NotableReport.region_code == region,
        NotableReport.obs_dt >= datetime.combine((now - HISTORY).date(), time()),
        NotableReport.obs_dt <= now,
        # Reviewed and not valid means rejected
        or_(NotableReport.is_valid, NotableReport.is_reviewed.is_(False)),
    )
    if known_by is None:
        stmt = stmt.where(NotableReport.withdrawn_at.is_(None))
    else:
        stmt = stmt.where(
            NotableReport.first_captured_at <= known_by,
            or_(NotableReport.withdrawn_at.is_(None), NotableReport.withdrawn_at > known_by),
        )
    return [
        Report(
            sub_id=r.sub_id,
            species_code=r.species_code,
            common_name=r.common_name,
            at=r.obs_dt,
            loc_id=r.loc_id,
            lat=r.lat,
            lng=r.lng,
            reviewed=r.is_valid,
        )
        for r in session.scalars(stmt)
    ]


def load_effort(session: Session, region: str, start: date, end: date) -> dict[date, int]:
    rows = session.execute(
        select(DailyStats.day, DailyStats.num_checklists).where(
            DailyStats.region_code == region, DailyStats.day.between(start, end)
        )
    )
    return {day: count for day, count in rows}


def species_codes(session: Session, episodes: list[Episode]) -> dict[str, str]:
    """One code per bird, so different forms of a species share it."""
    known = {
        name: code
        for name, code in session.execute(
            select(Species.common_name, Species.species_code).where(
                Species.common_name.in_({e.name for e in episodes})
            )
        )
    }
    for episode in episodes:
        known.setdefault(episode.name, min(r.species_code for r in episode.everything))
    return known


def status_at(
    session: Session, settings: Settings, species_code: str, at: datetime
) -> Status | None:
    """The status the app would have shown at `at`, or None if it didn't know of the bird yet."""
    known_by = at.replace(tzinfo=settings.zone).astimezone(UTC)
    episodes = build_episodes(load_reports(session, settings.region_code, at, known_by))
    codes = species_codes(session, episodes)
    matching = [e for e in episodes if codes[e.name] == species_code]
    if not matching:
        return None
    effort = load_effort(
        session, settings.region_code, (at - HISTORY).date(), (at - EFFORT_LAG).date()
    )
    return status_of(max(matching, key=lambda e: e.last), effort, at, settings.zone)


def list_rarities(session: Session, settings: Settings, now: datetime) -> list[Rarity]:
    region = settings.region_code
    episodes = build_episodes(load_reports(session, region, now))
    if not episodes:
        return []
    effort = load_effort(session, region, (now - HISTORY).date(), now.date())
    codes = species_codes(session, episodes)
    loc_ids = {r.loc_id for e in episodes for r in e.reports if r.loc_id}
    locations = {
        location.loc_id: location
        for location in session.scalars(select(Location).where(Location.loc_id.in_(loc_ids)))
    }
    names = _hotspot_names(session, locations)
    typical = {
        code: mean
        for code, mean in session.execute(
            select(ChecklistFrequency.species_code, func.avg(ChecklistFrequency.frequency))
            .where(ChecklistFrequency.region_code == region)
            .group_by(ChecklistFrequency.species_code)
        )
    }

    today, yesterday = now.date(), now.date() - timedelta(days=1)
    rarities = []
    for episode in episodes:
        code = codes[episode.name]
        hotspots, area = _where(episode, locations, names)
        by_day = episode.outings_by_day()
        reason = None
        if typical:
            rare = typical.get(code, 0.0) < RARE_MEAN_FREQUENCY
            reason = "Rare in this county" if rare else "Unusual date, count or form"
        rarities.append(
            Rarity(
                species_code=code,
                common_name=episode.name,
                status=status_of(episode, effort, now, settings.zone),
                reason=reason,
                first_reported=episode.first,
                last_reported=episode.last,
                outings=episode.outings,
                outings_today=by_day[today],
                outings_yesterday=by_day[yesterday],
                days_reported=len(by_day),
                unreviewed=not any(r.reviewed for r in episode.everything),
                hotspots=hotspots,
                area=area,
                is_current=episode.last.date() >= (now - CURRENT).date(),
            )
        )
    return sorted(rarities, key=lambda r: r.last_reported, reverse=True)


def _where(
    episode: Episode, locations: dict[str, Location], names: dict[str, str]
) -> tuple[list[str], str | None]:
    """Public hotspots this bird was itself reported from, or else only an area.

    Never the nearest hotspot, and never the middle of the pins: either could point
    at someone's yard.
    """
    public: Counter[str] = Counter()
    private: Counter[str] = Counter()
    for report in episode.reports:
        location = locations.get(report.loc_id or "")
        raw_name = names.get(report.loc_id or "")
        shown = public_location(location, raw_name)
        if shown.loc_id is None:
            private[shown.name or ""] += 1
        elif shown.name:
            public[shown.name] += 1
    if public:
        return [name for name, _ in public.most_common(MAX_HOTSPOTS)], None
    return [], private.most_common(1)[0][0] if private else None


def _hotspot_names(session: Session, locations: dict[str, Location]) -> dict[str, str]:
    public_ids = [i for i, location in locations.items() if not location.is_private]
    rows = session.execute(
        select(Location.loc_id, Location.public_name).where(Location.loc_id.in_(public_ids))
    )
    return {loc_id: name for loc_id, name in rows if name}
