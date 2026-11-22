"""One request budget shared by everything that calls eBird."""

import fcntl
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, text

_LOCK_ID = 0xEB12D  # arbitrary, but must be the same in every process
_LOCK_FILE = Path(tempfile.gettempdir()) / "fieldodds-ebird.lock"


@contextmanager
def request_slot(interval: float, engine: Engine | None = None) -> Iterator[None]:
    """Let one request through at a time, at least `interval` seconds after the last.

    The wait happens while holding the lock and before the request, so the gap holds
    without storing a timestamp, even if the previous caller just exited or crashed.

    Postgres provides the lock across containers. Without Postgres (local SQLite), a
    file lock covers the processes on this machine.
    """
    if interval <= 0:
        yield
    elif engine is not None and engine.dialect.name == "postgresql":
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": _LOCK_ID})
            try:
                time.sleep(interval)
                yield
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": _LOCK_ID})
    else:
        with _LOCK_FILE.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)  # released when the file closes
            time.sleep(interval)
            yield
