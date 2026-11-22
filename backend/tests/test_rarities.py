"""Rarity episodes, statuses, the pulls and the search log.

The replay follows the day-by-day shape of a real week-long chase: how many outings each
day, first and last report times, county effort. The bird, places and coordinates are made up.
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import respx
from sqlalchemy import func, select

from app.models import DailyStats, Location, NotableReport, RawResponse
from app.pipeline import run_job
from app.pipeline.schedule import run_if_due
from app.rarities.daylight import sunrise
from app.rarities.episodes import Report, base_name, build_episodes
from app.rarities.service import status_at
from app.rarities.status import Status, status_of
from tests.conftest import BASE_URL, REGION, load_fixture

ZONE = ZoneInfo("America/Chicago")
LAT, LNG = 45.0, -93.0
BIRD = "Example Flycatcher"

# day, outings, first report, last report
CHASE = [
    (date(2026, 10, 31), 22, "07:40", "16:03"),
    (date(2026, 11, 1), 14, "13:26", "15:41"),
    (date(2026, 11, 2), 4, "08:11", "09:35"),
    (date(2026, 11, 3), 9, "07:40", "15:15"),
    (date(2026, 11, 4), 8, "09:27", "14:51"),
    (date(2026, 11, 5), 6, "07:10", "16:49"),
    (date(2026, 11, 6), 13, "07:20", "15:31"),
]
EFFORT = {
    date(2026, 11, 5): 51,
    date(2026, 11, 6): 70,
    date(2026, 11, 7): 92,
    date(2026, 11, 8): 51,
}


def report(n, at, name=BIRD, lat=LAT, lng=LNG, loc=None):
    return Report(f"S{n}", "exafly", name, at, loc or f"L{n}", lat, lng)


def chase_reports():
    reports = []
    for day, count, first, last in CHASE:
        start = datetime.fromisoformat(f"{day}T{first}")
        end = datetime.fromisoformat(f"{day}T{last}")
        for i in range(count):
            at = start + (end - start) * i / (count - 1)
            n = len(reports)
            reports.append(report(n, at, lat=LAT + (n % 5) * 0.0005))
    return reports


def status_seen_at(moment: str):
    """Only what would have been known then: reports so far, counts two days late."""
    now = datetime.fromisoformat(moment)
    [episode] = build_episodes([r for r in chase_reports() if r.at <= now])
    effort = {d: n for d, n in EFFORT.items() if d <= now.date() - timedelta(days=2)}
    return status_of(episode, effort, now, ZONE)


@pytest.mark.parametrize(
    ("moment", "status"),
    [
        ("2026-10-31T07:45", Status.SINGLE_REPORT),
        ("2026-10-31T12:00", Status.BEING_SEEN),
        ("2026-10-31T22:00", Status.BEING_SEEN),  # darkness isn't evidence
        ("2026-11-01T06:00", Status.BEING_SEEN),  # nobody has had light to look
        ("2026-11-01T11:00", Status.NO_NEWS),  # the foggy morning: not "gone"
        ("2026-11-01T13:30", Status.BEING_SEEN),
        ("2026-11-04T12:30", Status.BEING_SEEN),
        ("2026-11-06T16:00", Status.BEING_SEEN),
        ("2026-11-07T11:00", Status.NO_NEWS),
        ("2026-11-08T11:00", Status.NO_NEWS),  # Saturday's count isn't in yet
        ("2026-11-09T06:30", Status.PROBABLY_GONE),  # 92 checklists, none with the bird
    ],
)
def test_replay(moment, status):
    assert status_seen_at(moment) == status


def test_never_gone_while_it_was_still_being_reported():
    moment = datetime(2026, 10, 31, 8)
    while moment <= datetime(2026, 11, 6, 15):
        assert status_seen_at(moment.isoformat()) != Status.PROBABLY_GONE
        moment += timedelta(hours=1)


def silent_for(outings, counted):
    """A bird reported by `outings` on Nov 2 (of 50 checklists), then `counted` silent days."""
    first = datetime(2026, 11, 2, 9)
    [episode] = build_episodes([report(i, first + timedelta(hours=i / 4)) for i in range(outings)])
    effort = {date(2026, 11, 2): 50}
    effort |= {date(2026, 11, 3) + timedelta(days=i): n for i, n in enumerate(counted)}
    return status_of(episode, effort, datetime(2026, 11, 8, 12), ZONE)


def test_silence_counts_in_proportion_to_looking():
    assert silent_for(10, []) == Status.NO_NEWS
    assert silent_for(10, [5]) == Status.NO_NEWS
    assert silent_for(10, [20]) == Status.NO_NEW_REPORTS
    assert silent_for(10, [60]) == Status.PROBABLY_GONE


def test_a_single_report_takes_far_more_silence_to_write_off():
    assert silent_for(1, [60]) == Status.NO_NEWS
    assert silent_for(1, [200, 200, 100]) == Status.PROBABLY_GONE


def test_a_slow_decline_weakens_the_evidence():
    reports = [report(i, datetime(2026, 11, 2, 8, i)) for i in range(20)]
    reports += [report(50 + i, datetime(2026, 11, 3, 8, i)) for i in range(2)]
    [episode] = build_episodes(reports)
    effort = {date(2026, 11, 2): 50, date(2026, 11, 3): 50, date(2026, 11, 4): 50}
    assert status_of(episode, effort, datetime(2026, 11, 6, 12), ZONE) == Status.NO_NEWS


def test_shared_checklists_are_one_outing():
    at = datetime(2026, 11, 2, 9)
    [episode] = build_episodes([report(n, at, loc="L-same") for n in range(5)])
    assert episode.outings == 1
    assert status_of(episode, {}, at, ZONE) == Status.SINGLE_REPORT


def test_forms_merge_and_distant_birds_do_not():
    at = datetime(2026, 11, 2, 9)
    forms = [report(1, at, "Red Crossbill (type 2)"), report(2, at, "Red Crossbill (type 4)")]
    assert [e.name for e in build_episodes(forms)] == ["Red Crossbill"]
    assert len(build_episodes([report(1, at), report(2, at, lat=LAT + 1)])) == 2
    assert base_name("Scissor-tailed Flycatcher") == "Scissor-tailed Flycatcher"


def test_a_new_visit_after_a_week_is_a_new_episode():
    at = datetime(2026, 11, 2, 9)
    assert len(build_episodes([report(1, at), report(2, at + timedelta(days=8))])) == 2


def test_stray_pin_is_counted_but_does_not_move_the_bird():
    reports = chase_reports()
    stray = report(999, datetime(2026, 11, 2, 9), lat=LAT + 0.095)  # about 10 km off
    [episode] = build_episodes([*reports, stray])
    [without] = build_episodes(reports)
    assert episode.strays == [stray]
    assert episode.center == without.center


def test_sunrise_matches_published_times_within_a_few_minutes():
    # Minneapolis, the day after clocks went back
    found = sunrise(date(2026, 11, 2), 44.98, -93.27, ZONE)
    assert found is not None
    assert abs(found - datetime(2026, 11, 2, 6, 54)) < timedelta(minutes=6)


# --- pulls ---------------------------------------------------------------------------


def notable(sub="S1", days_ago=1, private=True, **extra):
    day = datetime.now(UTC).date() - timedelta(days=days_ago)
    return {
        "speciesCode": "exafly",
        "comName": BIRD,
        "sciName": "Exemplum tyrannus",
        "locId": "LPRIVATE" if private else "LPUBLIC",
        "locName": "999 Example Lane (10.12345, 20.54321)" if private else "Example Trail",
        "lat": 10.12345 if private else 10.1301,
        "lng": 20.54321 if private else 20.5402,
        "obsDt": f"{day} 00:01" if private else f"{day} 00:02",
        "obsValid": True,
        "obsReviewed": True,
        "locationPrivate": private,
        "subId": sub,
        **extra,
    }


@pytest.fixture
def ebird():
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def pull(ctx, ebird):
    def _pull(*records):
        ebird.get(url__regex=r".*/recent/notable.*").respond(json=list(records))
        return run_job("notable_obs", ctx)

    return _pull


def test_notable_pull_never_stores_observer_names(ctx, ebird, pull):
    assert pull(notable(userDisplayName="Secret Person", firstName="Secret")).status == "success"
    assert "detail=simple" in str(ebird.calls.last.request.url)
    assert "Secret" not in str(ctx.session.scalar(select(RawResponse.payload)))


def test_removed_report_is_withdrawn_then_restored(ctx, pull, api):
    pull(notable())
    pull()
    assert ctx.session.scalar(select(NotableReport.withdrawn_at)) is not None
    assert api.get("/api/rarities").json()["items"] == []
    pull(notable())
    assert len(api.get("/api/rarities").json()["items"]) == 1
    assert ctx.session.scalar(select(func.count()).select_from(NotableReport)) == 1


def test_ageing_out_of_the_window_is_not_withdrawn(ctx, pull):
    pull(notable(days_ago=30))
    pull()
    assert ctx.session.scalar(select(NotableReport.withdrawn_at)) is None


def test_unreviewed_is_shown_and_marked_but_rejected_is_hidden(pull, api):
    pull(notable(obsValid=False, obsReviewed=False))
    assert api.get("/api/rarities").json()["items"][0]["unreviewed"] is True
    pull(notable(obsValid=False, obsReviewed=True))
    assert api.get("/api/rarities").json()["items"] == []


def test_private_rarity_shows_no_pin(pull, api):
    pull(notable())
    response = api.get("/api/rarities")
    item = response.json()["items"][0]
    assert item["hotspots"] == []
    assert item["area"] == "Private location"
    for secret in ("999 Example", "10.12345", "20.54321", "LPRIVATE", '"S1"'):
        assert secret not in response.text


def test_only_public_hotspots_it_was_reported_from_are_named(ctx, pull, api):
    ctx.session.add(
        Location(
            loc_id="LNEARBY", is_private=False, lat=10.124, lng=20.543, public_name="Nearest Park"
        )
    )
    pull(notable(), notable(sub="S2", private=False))
    response = api.get("/api/rarities")
    item = response.json()["items"][0]
    assert item["hotspots"] == ["Example Trail"]
    assert item["area"] is None
    assert "Nearest Park" not in response.text
    assert "999 Example" not in response.text


def test_hotspot_turned_private_loses_its_name(ctx, pull, api):
    pull(notable(private=False))
    pull(notable(private=False, locationPrivate=True))
    assert "Example Trail" not in api.get("/api/rarities").text
    assert ctx.session.get(Location, "LPUBLIC").public_name is None


def effort_days(ctx, ebird):
    route = ebird.get(url__regex=r".*/product/stats/.*").respond(
        json=load_fixture("daily_stats.json")
    )
    assert run_job("checklist_effort", ctx).status == "success"
    return route.call_count


def test_effort_is_one_call_on_first_run_and_none_on_a_rerun(ctx, ebird):
    assert effort_days(ctx, ebird) == 1
    assert ctx.session.scalar(select(DailyStats.day)) == ctx.settings.today() - timedelta(days=2)
    assert run_job("checklist_effort", ctx).rows_written == 0


@pytest.mark.parametrize(("latest_age", "calls"), [(3, 1), (5, 3), (40, 8)])
def test_effort_catches_up_one_call_per_missed_day_up_to_seven(ctx, ebird, latest_age, calls):
    ctx.session.add(
        DailyStats(
            region_code=REGION,
            day=ctx.settings.today() - timedelta(days=latest_age),
            num_checklists=1,
            num_contributors=1,
            num_species=1,
        )
    )
    ctx.session.commit()
    assert effort_days(ctx, ebird) == calls


def test_default_schedule_is_four_calls_a_day(ctx, ebird):
    ebird.get(url__regex=r".*/recent/notable.*").respond(json=[])
    ebird.get(url__regex=r".*/recent\?.*").respond(json=[])
    ebird.get(url__regex=r".*/product/stats/.*").respond(json=load_fixture("daily_stats.json"))
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    for minutes in range(0, 24 * 60, 10):
        now = today + timedelta(minutes=minutes)
        for run in run_if_due(ctx, now):
            run.started_at = now  # as if the wall clock read `now`
        ctx.session.commit()

    assert ebird.calls.call_count == 4


def test_late_wake_collapses_missed_rarity_slots(ctx, ebird):
    route = ebird.get(url__regex=r".*/recent/notable.*").respond(json=[])
    ctx.settings.pipeline_jobs = ["notable_obs"]
    run_if_due(ctx, datetime.now(UTC).replace(hour=23, minute=0))
    assert route.call_count == 1


# --- search log ----------------------------------------------------------------------

APP = {"X-Field-Odds": "1"}


def test_log_list_and_remove(pull, api):
    pull(notable())
    body = {"species_code": "exafly", "found": False}
    saved = api.post("/api/searches", json=body, headers=APP)
    assert saved.status_code == 201
    assert saved.json()["common_name"] == BIRD
    assert saved.json()["found"] is False
    assert len(api.get("/api/searches", headers=APP).json()) == 1
    assert api.delete(f"/api/searches/{saved.json()['id']}", headers=APP).status_code == 204
    assert api.get("/api/searches", headers=APP).json() == []


def test_log_needs_the_app_header(pull, api):
    pull(notable())
    assert (
        api.post("/api/searches", json={"species_code": "exafly", "found": True}).status_code == 403
    )
    assert api.get("/api/searches").status_code == 403
    assert api.delete("/api/searches/1").status_code == 403


@pytest.mark.parametrize(
    ("extra", "code"),
    [
        ({"lat": 10.1}, 422),
        ({"searched_at": "2099-01-01T12:00"}, 422),
        ({"species_code": "nosuch"}, 404),
    ],
)
def test_log_rejects_locations_future_times_and_unknown_birds(pull, api, extra, code):
    pull(notable())
    body = {"species_code": "exafly", "found": True, **extra}
    assert api.post("/api/searches", json=body, headers=APP).status_code == code


def test_backdated_log_uses_only_what_was_known_then(ctx, pull, api):
    pull(notable())  # captured now, for a bird seen yesterday
    earlier = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
    body = {"species_code": "exafly", "found": True, "searched_at": earlier.isoformat()}
    assert api.post("/api/searches", json=body, headers=APP).json()["status_then"] is None

    captured = ctx.session.scalar(select(NotableReport))
    captured.first_captured_at = datetime.now(UTC) - timedelta(hours=2)
    ctx.session.commit()
    assert status_at(ctx.session, ctx.settings, "exafly", earlier) == Status.SINGLE_REPORT
