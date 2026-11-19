"""End-to-end: mocked eBird → jobs → db → model → API."""

from datetime import timedelta

import pytest
import respx
from sqlalchemy import func, select
from tenacity import stop_after_attempt

from app.ebird import EBirdClient
from app.models import Observation, PipelineRun, RawResponse
from app.pipeline import run_job, run_pipeline
from tests.conftest import BASE_URL, load_fixture


@pytest.fixture
def ebird():
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        mock.get(url__regex=r".*/data/obs/.*/historic/.*").respond(
            json=load_fixture("historic_day.json")
        )
        mock.get(url__regex=r".*/data/obs/.*/recent").respond(
            json=load_fixture("historic_day.json")
        )
        mock.get(url__regex=r".*/product/stats/.*").respond(json=load_fixture("daily_stats.json"))
        mock.get("/ref/taxonomy/ebird").respond(json=load_fixture("taxonomy.json"))
        yield mock


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_historic_job_is_idempotent_and_archives_raw(ctx, ebird):
    yesterday = ctx.settings.today() - timedelta(days=1)
    first = run_job("historic_day", ctx, day=yesterday)
    second = run_job("historic_day", ctx, day=yesterday)

    assert first.status == second.status == "success"
    assert _count(ctx.session, Observation) == 3  # second run added no duplicates
    assert _count(ctx.session, RawResponse) == 2  # but every payload is archived


def test_failed_job_is_recorded_and_pipeline_continues(ctx, ebird, monkeypatch):
    ebird.get(url__regex=r".*/data/obs/.*/recent").respond(500)
    monkeypatch.setattr(EBirdClient.get.retry, "stop", stop_after_attempt(1))

    runs = run_pipeline(ctx, ["recent_obs", "daily_stats"])

    assert [r.status for r in runs] == ["failed", "success"]
    assert "HTTPStatusError" in (runs[0].error or "")
    assert _count(ctx.session, PipelineRun) == 2


def test_full_pipeline_then_api(ctx, ebird, api):
    run_job("taxonomy", ctx)
    for name in ("historic_day", "daily_stats", "compute_predictions"):
        assert run_job(name, ctx).status == "success"

    resp = api.get("/api/predictions/today")
    assert resp.status_code == 200
    body = resp.json()
    assert body["for_date"] == ctx.settings.today().isoformat()
    codes = [i["species_code"] for i in body["items"]]
    assert set(codes) == {"amecro", "baleag"}  # "gull sp." is excluded
    crow = body["items"][0]
    assert crow["common_name"] in {"American Crow", "Bald Eagle"}
    assert 0 < crow["likelihood"] <= 1
    assert crow["last_location"] == "Discovery Park"

    assert api.get("/api/predictions/today", params={"min_likelihood": 1.01}).status_code == 422

    detail = api.get("/api/species/baleag").json()
    assert detail["family_common_name"] == "Hawks, Eagles, and Kites"
    assert len(detail["recent_observations"]) == 1

    runs = api.get("/api/pipeline/runs").json()
    assert runs[0]["job_name"] == "compute_predictions"


def test_api_empty_state_and_errors(api):
    body = api.get("/api/predictions/today").json()
    assert body["items"] == [] and body["for_date"] is None
    assert api.get("/api/species/nope").status_code == 404
    assert api.post("/api/pipeline/run/taxonomy").status_code == 403
    assert api.get("/health").json()["status"] == "ok"
