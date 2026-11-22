"""What can honestly be said about a rarity right now.

Failed searches mostly go unreported, and more often *because* they failed. So this
never counts failures and never gives a chance of finding the bird. It counts missing
successes: silence means something in proportion to how many reports we'd have expected.

    expected = share of county checklists that had it x checklists on each silent day
               x an allowance for interest fading once local birders have seen it

Days without a checklist count yet add nothing, which is what keeps a quiet, foggy
morning from reading as "gone".
"""

from datetime import date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from app.rarities.daylight import sunrise
from app.rarities.episodes import Episode

# Chasers run out: assume a third of the interest remains once reports stop.
INTEREST_REMAINING = 1 / 3
# With 3 reports expected, seeing none happens about 5% of the time by chance.
GONE_EXPECTED = 3.0
QUIET_EXPECTED = 1.0
# Yesterday's bird is still "being seen" until people have had some light to look today.
MORNING_GRACE = timedelta(hours=2)
SHARE_DAYS = 3


class Status(StrEnum):
    BEING_SEEN = "being_seen"
    SINGLE_REPORT = "single_report"
    NO_NEWS = "no_news"
    NO_NEW_REPORTS = "no_new_reports"
    PROBABLY_GONE = "probably_gone"


def expected_missing_reports(episode: Episode, effort: dict[date, int], today: date) -> float:
    """Reports we'd expect on the completed days since the last one, if it were still there."""
    seen = episode.outings_by_day()
    days = sorted(d for d in seen if effort.get(d))[-SHARE_DAYS:]
    if not days:
        return 0.0
    average = sum(seen[d] for d in days) / sum(effort[d] for d in days)
    latest = seen[days[-1]] / effort[days[-1]]
    share = min(average, latest, 1.0)  # a slow decline weakens the evidence

    looked = sum(n for day, n in effort.items() if episode.last.date() < day < today)
    return share * looked * INTEREST_REMAINING


def status_of(episode: Episode, effort: dict[date, int], now: datetime, zone: ZoneInfo) -> Status:
    """`now` is local and naive, like eBird's observation times."""
    age = (now.date() - episode.last.date()).days
    several = episode.outings > 1

    if age <= 0:
        return Status.BEING_SEEN if several else Status.SINGLE_REPORT
    if age == 1:
        if not several:
            return Status.SINGLE_REPORT
        center = episode.center
        rises = sunrise(now.date(), *center, zone) if center else None
        searching_since = rises or now.replace(hour=8, minute=0, second=0, microsecond=0)
        barely_looked = now < searching_since + MORNING_GRACE
        return Status.BEING_SEEN if barely_looked else Status.NO_NEWS

    expected = expected_missing_reports(episode, effort, now.date())
    if expected >= GONE_EXPECTED:
        return Status.PROBABLY_GONE
    if expected >= QUIET_EXPECTED:
        return Status.NO_NEW_REPORTS
    return Status.NO_NEWS
