"""Histogram import and the per-checklist model. All data here is made up."""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.histogram import check_filename, parse_histogram, period_of
from app.models import ChecklistFrequency, Observation, Species
from app.pipeline import run_job
from app.pipeline.schedule import run_if_due
from tests.conftest import REGION

FILENAME = f"ebird_{REGION}__2020_2026_1_12_barchart.txt"


def chart(**species: float) -> str:
    def row(name, values):
        return "\t".join([name, *map(str, values)]) + "\t\n"

    body = "\n\nNumber of taxa: \t3\n\n\tJan\t\t\t\tFeb\n"
    body += row("Sample Size:", [100.0 + p for p in range(48)]) + "\n"
    for name, value in species.items():
        body += row(name.replace("_", " "), [value] * 48)
    return body


@pytest.fixture
def load(ctx, tmp_path):
    for code, name, category in (
        ("amecro", "American Crow", "species"),
        ("baleag", "Bald Eagle", "species"),
        ("gulls", "gull sp.", "spuh"),
    ):
        ctx.session.add(
            Species(species_code=code, common_name=name, sci_name=name, category=category)
        )
    ctx.session.commit()

    def _load(text, filename=FILENAME):
        path = tmp_path / "chart.txt"
        path.write_text(text)
        return run_job("import_histogram", ctx, path=str(path), filename=filename)

    return _load


@pytest.mark.parametrize(
    ("day", "period"),
    [
        (date(2026, 1, 1), 0),
        (date(2026, 1, 7), 0),
        (date(2026, 1, 8), 1),
        (date(2026, 1, 21), 2),
        (date(2026, 1, 22), 3),
        (date(2026, 1, 31), 3),
        (date(2028, 2, 29), 7),
        (date(2026, 11, 22), 43),
        (date(2026, 12, 31), 47),
    ],
)
def test_period_of(day, period):
    assert period_of(day) == period


@pytest.mark.parametrize(
    "filename",
    [
        "ebird_US-XX-001__2020_2026_1_12_barchart.txt",
        f"ebird_{REGION}__2020_2026_5_6_barchart.txt",
        "renamed.txt",
    ],
)
def test_rejects_the_wrong_file(filename):
    with pytest.raises(ValueError):
        check_filename(filename, REGION)


@pytest.mark.parametrize(
    "text",
    ["", "Sample Size:\t1\t2\n", chart(A=0.5) + "B\t0.5\n", chart(A=1.5), chart()],
)
def test_rejects_malformed_files(text):
    with pytest.raises(ValueError):
        parse_histogram(text)


def test_import_and_predict(ctx, load, api):
    assert load(chart(American_Crow=0.5, Bald_Eagle=0.004, **{"gull sp.": 0.3})).status == "success"
    assert run_job("compute_predictions", ctx).status == "success"

    items = api.get("/api/predictions/today").json()["items"]
    assert [(i["species_code"], i["likelihood"]) for i in items] == [
        ("amecro", 0.5),
        ("baleag", 0.004),
    ]
    assert items[0]["sample_size"] == 100 + period_of(ctx.settings.today())


def test_reimport_replaces_old_data(ctx, load):
    load(chart(American_Crow=0.5, Bald_Eagle=0.2))
    load(chart(American_Crow=0.7))
    rows = ctx.session.scalars(select(ChecklistFrequency)).all()
    assert len(rows) == 48
    assert {r.frequency for r in rows} == {0.7}


def test_bad_import_keeps_existing_data(ctx, load):
    load(chart(American_Crow=0.5))
    assert load(chart(Mystery_Bird=0.5)).status == "failed"
    assert ctx.session.scalar(select(func.count()).select_from(ChecklistFrequency)) == 48


@pytest.mark.parametrize(("age", "expected"), [(0, 0), (7, 7), (8, None)])
def test_recent_badge(ctx, load, api, age, expected):
    load(chart(American_Crow=0.5))
    seen = ctx.settings.today() - timedelta(days=age)
    ctx.session.add(
        Observation(
            region_code=REGION,
            species_code="amecro",
            common_name="American Crow",
            sci_name="Corvus brachyrhynchos",
            sub_id="S1",
            obs_date=seen,
            obs_dt=datetime.combine(seen, datetime.min.time()),
            source="recent",
        )
    )
    ctx.session.commit()
    run_job("compute_predictions", ctx)

    item = api.get("/api/predictions/today").json()["items"][0]
    assert (item["reported_days_ago"], item["likelihood"]) == (expected, 0.5)


def test_percentages_update_daily_even_without_a_key(ctx):
    assert "compute_predictions" in Settings(_env_file=None).pipeline_jobs
    ctx.settings.ebird_api_key = ""
    ctx.settings.schedule_hour = 0
    assert [r.job_name for r in run_if_due(ctx)] == ["compute_predictions"]
