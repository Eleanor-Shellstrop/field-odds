from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert, select

from app.geo.labels import label_locations
from app.geo.sources import PLACE, SUBDIVISION, NamedArea, hotspot_area, read_census
from app.models import Boundary, Location, Observation
from app.pipeline.base import Job, JobContext
from app.pipeline.registry import register


@register
class ImportBoundariesJob(Job):
    name = "import_boundaries"
    description = "Load Census boundaries and label private locations (CLI: import-boundaries)"
    uses_api = False

    def execute(
        self, ctx: JobContext, path: str = "", hotspot_areas: list[str] | None = None, **_: Any
    ) -> int:
        if not path:
            raise ValueError("A folder of Census boundary files is required")
        areas: list[NamedArea] = []
        for kind, priority in (("place", PLACE), ("cousub", SUBDIVISION)):
            files = sorted(Path(path).rglob(f"cb_*_{kind}_500k.zip"))
            if len(files) != 1:
                raise ValueError(f"Expected one cb_*_{kind}_500k.zip, found {len(files)}")
            areas += read_census(files[0], priority)

        for prefix in hotspot_areas or []:
            points = ctx.session.execute(
                select(Location.lng, Location.lat)
                .join(Observation, Observation.loc_id == Location.loc_id)
                .where(
                    Location.is_private.is_(False),
                    Location.lat.is_not(None),
                    Location.lng.is_not(None),
                    Observation.region_code == ctx.region,
                    Observation.loc_name.istartswith(prefix, autoescape=True),
                )
                .distinct()
            ).all()
            coordinates = [(x, y) for x, y in points if x is not None and y is not None]
            areas.append(hotspot_area(prefix, coordinates))

        ctx.session.execute(delete(Boundary))
        ctx.session.execute(insert(Boundary), [vars(a) for a in areas])
        label_locations(ctx.session, ctx.session.scalars(select(Location)).all())
        return len(areas)
