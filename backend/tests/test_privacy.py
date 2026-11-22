"""Private locations must never leave the API. Every place and coordinate here is made up."""

import importlib.util
import zipfile
from datetime import datetime
from pathlib import Path

import pytest
import shapefile
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from shapely.geometry import box

from app.ebird.schemas import EBirdObservation
from app.geo.labels import AreaLookup
from app.geo.sources import PLACE, SUBDIVISION, display_name, hotspot_area
from app.models import Boundary, Location, PipelineRun, Prediction, RawResponse
from app.pipeline import run_job
from app.pipeline.store import upsert_observations
from app.privacy import PRIVATE, public_location
from tests.conftest import REGION

SECRET_NAME = "999 Example Lane (10.12345, 20.54321)"
SECRETS = ("999 Example", "10.12345", "20.54321", "LPRIVATE")


def boundary(name, priority, area, bounds=(20, 10, 21, 11)):
    return Boundary(name=name, priority=priority, area_km2=area, wkt=box(*bounds).wkt)


def sighting(loc_id="LPRIVATE", name=SECRET_NAME, lat=10.12345, lng=20.54321, **extra):
    return EBirdObservation(
        species_code="amecro",
        common_name="American Crow",
        sci_name="Corvus brachyrhynchos",
        sub_id=f"S-{loc_id}",
        obs_dt=datetime(2026, 11, 1, 8),
        loc_id=loc_id,
        loc_name=name,
        lat=lat,
        lng=lng,
        **extra,
    )


@pytest.fixture
def responses(ctx, api):
    def _responses():
        ctx.session.add(
            Prediction(
                region_code=REGION,
                for_date=ctx.settings.today(),
                species_code="amecro",
                likelihood=0.5,
                model_name="checklist_frequency_v1",
            )
        )
        ctx.session.commit()
        return api.get("/api/predictions/today"), api.get("/api/species/amecro")

    return _responses


def test_private_location_becomes_an_area(ctx, responses):
    ctx.session.add(boundary("Example Township", SUBDIVISION, 90))
    upsert_observations(ctx.session, REGION, [sighting(location_private=True)], "recent")

    today, detail = responses()

    expected = f"{PRIVATE} in Example Township"
    assert today.json()["items"][0]["last_location"] == expected
    seen = detail.json()["recent_observations"][0]
    assert seen["loc_name"] == expected
    assert (seen["loc_id"], seen["lat"], seen["lng"]) == (None, None, None)
    assert not any(secret in today.text + detail.text for secret in SECRETS)


def test_missing_flag_is_private(ctx, responses):
    upsert_observations(ctx.session, REGION, [sighting()], "recent")
    today, detail = responses()
    assert today.json()["items"][0]["last_location"] == PRIVATE
    assert not any(secret in today.text + detail.text for secret in SECRETS)


def test_unknown_location_is_private(ctx, responses):
    upsert_observations(ctx.session, REGION, [sighting(location_private=False)], "recent")
    ctx.session.flush()
    ctx.session.delete(ctx.session.get(Location, "LPRIVATE"))
    today, detail = responses()
    assert not any(secret in today.text + detail.text for secret in SECRETS)


def test_hotspot_is_unchanged(ctx, responses):
    hotspot = sighting("L1", "Example Park", location_private=False)
    upsert_observations(ctx.session, REGION, [hotspot], "recent")
    today, detail = responses()
    assert today.json()["items"][0]["last_location"] == "Example Park"
    assert detail.json()["recent_observations"][0]["lat"] == 10.12345


def test_privacy_follows_ebird_when_it_changes(ctx):
    upsert_observations(ctx.session, REGION, [sighting(location_private=False)], "recent")
    ctx.session.commit()
    upsert_observations(ctx.session, REGION, [sighting(location_private=True)], "recent")
    ctx.session.commit()
    location = ctx.session.get(Location, "LPRIVATE")
    assert public_location(location, SECRET_NAME).name == PRIVATE


def test_private_wins_within_one_response(ctx):
    mixed = [sighting(location_private=True), sighting(location_private=False)]
    upsert_observations(ctx.session, REGION, mixed, "recent")
    assert ctx.session.get(Location, "LPRIVATE").is_private


def test_named_area_beats_place_beats_township():
    township = boundary("Township", SUBDIVISION, 90)
    place = boundary("Town", PLACE, 10)
    named = boundary("Bog area", 0, 500)
    assert AreaLookup([township, place]).name_for(10.5, 20.5) == "Town"
    assert AreaLookup([township, place, named]).name_for(10.5, 20.5) == "Bog area"


def test_tiny_area_is_never_named():
    tiny_city = boundary("Tiny", PLACE, 0.3)
    same_as_subdivision = boundary("Tiny", SUBDIVISION, 0.3)
    assert AreaLookup([tiny_city, same_as_subdivision]).name_for(10.5, 20.5) is None


def test_contains_rather_than_nearest():
    assert AreaLookup([boundary("Town", PLACE, 50)]).name_for(11.001, 20.5) is None
    assert AreaLookup([]).name_for(10.5, 20.5) is None


def test_hotspot_outline():
    area = hotspot_area("Bog", [(20.0, 10.0), (20.2, 10.0), (20.1, 10.2)])
    lookup = AreaLookup(
        [Boundary(name=area.name, priority=area.priority, area_km2=area.area_km2, wkt=area.wkt)]
    )
    assert lookup.name_for(10.05, 20.1) == "Bog area"
    assert lookup.name_for(10.5, 20.5) is None
    with pytest.raises(ValueError):
        hotspot_area("Bog", [(20.0, 10.0)])


@pytest.mark.parametrize(
    ("lsad", "shown"),
    [
        ("25", "Example"),
        ("57", "Example"),
        ("44", "Example Township"),
        ("46", "Example unorganized territory"),
    ],
)
def test_display_names(lsad, shown):
    assert display_name("Example", "Example full", lsad) == shown


def test_import_labels_existing_locations(ctx, tmp_path):
    for kind, name, lsad in (("place", "Faraway", "25"), ("cousub", "Example", "44")):
        stem = tmp_path / f"cb_2025_00_{kind}_500k"
        with shapefile.Writer(str(stem), shapeType=shapefile.POLYGON) as writer:
            for column in ("NAME", "NAMELSAD", "LSAD"):
                writer.field(column, "C", size=100)
            for column in ("ALAND", "AWATER"):
                writer.field(column, "N", size=14)
            west = 50 if kind == "place" else 20
            corners = [[west, 10], [west, 11], [west + 1, 11], [west + 1, 10], [west, 10]]
            writer.poly([corners])
            writer.record(name, name, lsad, 90_000_000, 0)
        with zipfile.ZipFile(f"{stem}.zip", "w") as archive:
            for suffix in ("shp", "shx", "dbf"):
                archive.write(f"{stem}.{suffix}", f"{stem.name}.{suffix}")
    upsert_observations(ctx.session, REGION, [sighting(location_private=True)], "recent")
    ctx.session.commit()

    run = run_job("import_boundaries", ctx, path=str(tmp_path))

    assert run.status == "success", run.error
    assert ctx.session.get(Location, "LPRIVATE").area_name == "Example Township"


def test_pipeline_errors_do_not_quote_private_data(ctx, api):
    ctx.session.add(
        PipelineRun(job_name="recent_obs", params={}, status="failed", error=f"input={SECRET_NAME}")
    )
    ctx.session.commit()
    response = api.get("/api/pipeline/runs")
    assert response.json()[0]["error"]
    assert not any(secret in response.text for secret in SECRETS)


def test_migration_backfill_fails_closed(session):
    path = next((Path(__file__).parents[1] / "alembic/versions").glob("*location_privacy.py"))
    spec = importlib.util.spec_from_file_location("location_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    for payload in (
        [{"locId": "L1", "locationPrivate": False}, {"locId": "L2"}],
        [{"locId": "L3", "locationPrivate": True}],
        {"numChecklists": 4},
    ):
        session.add(RawResponse(endpoint="x", params={}, payload=payload))
    session.flush()

    with Operations.context(MigrationContext.configure(session.connection())):
        migration._backfill_locations()

    stored = dict(session.execute(sa.select(Location.loc_id, Location.is_private)).all())
    assert stored == {"L1": False, "L2": True, "L3": True}
