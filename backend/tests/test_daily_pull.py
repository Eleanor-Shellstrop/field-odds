"""Guarantees the daily pull makes: once a day, catch-up, capped retries, shared rate limit."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
import respx
from pydantic import ValidationError
from sqlalchemy import select

from app.config import Settings
from app.ebird.rate_limit import request_slot
from app.ebird.schemas import EBirdObservation
from app.models import Observation, PipelineRun
from app.pipeline.schedule import run_if_due
from app.pipeline.store import upsert_observations
from tests.conftest import BASE_URL, REGION, load_fixture

NOON = datetime(2026, 11, 22, 12, tzinfo=UTC)


@pytest.fixture
def recent():
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        yield mock.get(f"/data/obs/{REGION}/recent").respond(json=load_fixture("historic_day.json"))


def attempt(ctx, status, at):
    ctx.session.add(PipelineRun(job_name="recent_obs", params={}, status=status, started_at=at))
    ctx.session.commit()


def test_default_pull_is_one_call_for_seven_days(ctx, recent):
    assert [r.status for r in run_if_due(ctx, NOON)] == ["success"]
    assert recent.call_count == 1
    assert recent.calls.last.request.url.params["back"] == "7"


def test_waits_for_the_scheduled_hour(ctx, recent):
    assert run_if_due(ctx, NOON.replace(hour=5, minute=59)) == []
    assert not recent.called
    assert run_if_due(ctx, NOON.replace(hour=6, minute=0))


def test_success_today_means_no_more_calls(ctx, recent):
    attempt(ctx, "success", NOON.replace(hour=6))
    for hour in range(6, 24):
        assert run_if_due(ctx, NOON.replace(hour=hour)) == []
    assert not recent.called


def test_catches_up_late_in_the_day_after_days_off(ctx, recent):
    attempt(ctx, "success", NOON - timedelta(days=4))
    assert len(run_if_due(ctx, NOON.replace(hour=23, minute=50))) == 1
    assert recent.call_count == 1  # one call covers the missed days


@pytest.mark.parametrize("status", ["failed", "running"])  # "running" is left behind by a crash
def test_retries_after_an_hour(ctx, recent, status):
    attempt(ctx, status, NOON - timedelta(minutes=59))
    assert run_if_due(ctx, NOON) == []
    assert run_if_due(ctx, NOON + timedelta(minutes=2))


def test_gives_up_after_three_attempts_until_tomorrow(ctx, recent):
    for hour in (6, 7, 8):
        attempt(ctx, "failed", NOON.replace(hour=hour))
    assert run_if_due(ctx, NOON) == []
    assert run_if_due(ctx, NOON + timedelta(days=1))


def test_schedule_uses_local_time(ctx, recent):
    ctx.settings.tz = "America/Chicago"  # 06:00 CST is 12:00 UTC
    assert run_if_due(ctx, NOON - timedelta(minutes=1)) == []
    assert run_if_due(ctx, NOON)


def test_schedule_follows_daylight_saving(ctx, recent):
    ctx.settings.tz = "America/Chicago"  # 06:00 CDT is 11:00 UTC
    july = datetime(2026, 7, 22, 11, tzinfo=UTC)
    assert run_if_due(ctx, july - timedelta(minutes=1)) == []
    assert run_if_due(ctx, july)


def test_missing_key_is_not_an_attempt(ctx, recent):
    ctx.settings.ebird_api_key = ""
    assert run_if_due(ctx, NOON) == []
    assert ctx.session.scalars(select(PipelineRun)).all() == []


def test_recent_sightings_do_not_affect_likelihood(ctx):
    from app.ml import get_model

    target = NOON.date()
    sighting = EBirdObservation(
        species_code="amecro",
        common_name="American Crow",
        sci_name="Corvus brachyrhynchos",
        sub_id="S1",
        obs_dt=NOON.replace(tzinfo=None) - timedelta(days=1),
    )
    model = get_model(ctx.settings)

    upsert_observations(ctx.session, REGION, [sighting], source="recent")
    assert model.predict(ctx.session, REGION, target) == []

    # The same sighting arriving from the historic feed does count, and stays counted.
    upsert_observations(ctx.session, REGION, [sighting], source="historic")
    upsert_observations(ctx.session, REGION, [sighting], source="recent")
    assert ctx.session.scalars(select(Observation.source)).all() == ["historic"]
    assert len(model.predict(ctx.session, REGION, target)) == 1


def test_interval_cannot_be_set_faster_than_one_second():
    assert Settings(_env_file=None).ebird_min_interval == 1.1
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ebird_min_interval=0.5)


def test_concurrent_callers_are_spaced_out():
    def call(_):
        with request_slot(0.05):
            return time.monotonic()

    with ThreadPoolExecutor(4) as pool:
        times = sorted(pool.map(call, range(4)))
    assert all(b - a >= 0.045 for a, b in zip(times, times[1:], strict=False))
