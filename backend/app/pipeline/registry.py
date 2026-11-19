"""Job registry. To add a new eBird call: write a Job subclass in pipeline/jobs/,
decorate it with @register, and (optionally) add its name to PIPELINE_JOBS."""

from app.pipeline.base import Job

_JOBS: dict[str, type[Job]] = {}


def register[J: type[Job]](cls: J) -> J:
    if cls.name in _JOBS:
        raise ValueError(f"Duplicate job name: {cls.name}")
    _JOBS[cls.name] = cls
    return cls


def _load() -> None:
    import app.pipeline.jobs  # noqa: F401  (importing registers every job)


def get_job(name: str) -> Job:
    _load()
    try:
        return _JOBS[name]()
    except KeyError:
        raise KeyError(f"Unknown job '{name}'. Known: {', '.join(sorted(_JOBS))}") from None


def all_jobs() -> dict[str, type[Job]]:
    _load()
    return dict(_JOBS)
