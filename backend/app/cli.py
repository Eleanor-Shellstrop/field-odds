"""Command line entry point: `python -m app.cli --help`."""

import logging
from pathlib import Path

import typer
from sqlalchemy import select

from app.config import get_settings
from app.ml.frequency import sample_days
from app.models import DailyStats
from app.pipeline import run_job, run_pipeline
from app.pipeline.registry import all_jobs
from app.runtime import job_context

cli = typer.Typer(help="Field Odds pipeline commands", no_args_is_help=True)


@cli.callback()
def _setup(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)


@cli.command("list-jobs")
def list_jobs() -> None:
    """Show every registered job."""
    for name, job in sorted(all_jobs().items()):
        typer.echo(f"{name:22} {job.description}")


@cli.command("run-job")
def run_one(
    name: str,
    day: str | None = typer.Option(None, help="YYYY-MM-DD; defaults depend on the job"),
) -> None:
    """Run a single job now."""
    params = {"day": day} if day else {}
    with job_context() as ctx:
        run = run_job(name, ctx, **params)
    typer.echo(f"{run.job_name}: {run.status} ({run.rows_written} rows)")
    if run.status != "success":
        typer.echo(run.error or "", err=True)
        raise typer.Exit(1)


@cli.command("run-pipeline")
def run_all() -> None:
    """Run the scheduled pipeline (PIPELINE_JOBS) once, right now."""
    with job_context() as ctx:
        for run in run_pipeline(ctx):
            typer.echo(f"{run.job_name}: {run.status} ({run.rows_written} rows)")


@cli.command("seed-taxonomy")
def seed_taxonomy() -> None:
    """Load eBird species names. Run once, then about yearly."""
    run_one("taxonomy", None)


@cli.command("import-histogram")
def import_histogram(
    path: str,
    filename: str | None = typer.Option(None, help="Original name, when reading /dev/stdin"),
) -> None:
    """Load an eBird bar chart histogram file, then recompute today's likelihoods."""
    with job_context() as ctx:
        run = run_job("import_histogram", ctx, path=path, filename=filename or Path(path).name)
        if run.status != "success":
            typer.echo(run.error or "", err=True)
            raise typer.Exit(1)
        typer.echo(f"import_histogram: success ({run.rows_written} rows)")
        predicted = run_job("compute_predictions", ctx)
        typer.echo(f"compute_predictions: {predicted.status} ({predicted.rows_written} species)")
        if predicted.status != "success":
            raise typer.Exit(1)


@cli.command("import-boundaries")
def import_boundaries(
    path: str,
    hotspot_area: list[str] | None = typer.Option(
        None, help="Outline an area from hotspots whose names start with this. Repeatable."
    ),
) -> None:
    """Load Census boundary files and label private locations by area."""
    with job_context() as ctx:
        run = run_job(
            "import_boundaries", ctx, path=path, hotspot_areas=[a for a in hotspot_area or [] if a]
        )
        if run.status != "success":
            typer.echo(run.error or "", err=True)
            raise typer.Exit(1)
        typer.echo(f"import_boundaries: success ({run.rows_written} boundaries)")


@cli.command()
def backfill(
    years: int | None = typer.Option(None, help="Years of history (default MODEL_YEARS)"),
    force: bool = typer.Option(False, help="Re-fetch days that are already stored"),
) -> None:
    """Fetch the historic days the likelihood model needs for today's date.

    That's about years × (2 × window + 1) + recent days, at 2 API calls per day.
    Days already stored are skipped, so an interrupted backfill can just be run again.
    """
    s = get_settings()
    days = sorted(
        sample_days(
            s.today(),
            years or s.model_years,
            s.model_window_days,
            s.model_recent_days,
            s.model_recent_weight,
        )
    )
    with job_context() as ctx:
        done = set(
            ctx.session.scalars(
                select(DailyStats.day).where(DailyStats.region_code == s.region_code)
            )
        )
        todo = [d for d in days if force or d not in done]
        typer.echo(f"Backfilling {len(todo)} of {len(days)} days for {s.region_code}")
        with typer.progressbar(todo, label="days") as bar:
            for d in bar:
                run_job("historic_day", ctx, day=d)
                run_job("daily_stats", ctx, day=d)
        run = run_job("compute_predictions", ctx)
        typer.echo(f"compute_predictions: {run.status} ({run.rows_written} species)")


if __name__ == "__main__":
    cli()
