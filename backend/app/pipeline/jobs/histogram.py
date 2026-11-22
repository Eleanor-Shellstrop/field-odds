from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert, select

from app.histogram import check_filename, parse_histogram
from app.models import ChecklistFrequency, Species
from app.pipeline.base import Job, JobContext
from app.pipeline.registry import register


@register
class ImportHistogramJob(Job):
    name = "import_histogram"
    description = "Load an eBird bar chart histogram file (CLI: import-histogram)"
    uses_api = False

    def execute(self, ctx: JobContext, path: str = "", filename: str = "", **_: Any) -> int:
        check_filename(filename, ctx.region)
        histogram = parse_histogram(Path(path).read_text(encoding="utf-8"))

        codes = {
            name: code
            for name, code in ctx.session.execute(select(Species.common_name, Species.species_code))
        }
        if not codes:
            raise ValueError("No species names loaded yet: run `make taxonomy` first")
        # Skipping a name would silently drop that bird, so refuse the whole file instead.
        unknown = sorted(histogram.frequencies.keys() - codes.keys())
        if unknown:
            raise ValueError(
                f"{len(unknown)} names not in the taxonomy (run `make taxonomy`): {unknown[:10]}"
            )

        rows = [
            {
                "region_code": ctx.region,
                "species_code": codes[name],
                "period": period,
                "frequency": value,
                "sample_size": histogram.sample_sizes[period],
            }
            for name, values in histogram.frequencies.items()
            for period, value in enumerate(values)
        ]
        ctx.session.execute(
            delete(ChecklistFrequency).where(ChecklistFrequency.region_code == ctx.region)
        )
        ctx.session.execute(insert(ChecklistFrequency), rows)
        return len(rows)
