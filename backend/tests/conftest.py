import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import create_app
from app.config import Settings, get_settings
from app.db import get_session
from app.ebird import EBirdClient
from app.models import Base
from app.pipeline import JobContext

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://ebird.test/v2"
REGION = "US-WA-033"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        ebird_api_key="test-key",
        ebird_base_url=BASE_URL,
        region_code=REGION,
        tz="UTC",
        database_url="sqlite://",
        enable_manual_triggers=False,
    )


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s


@pytest.fixture
def ctx(session: Session, settings: Settings) -> Iterator[JobContext]:
    c = JobContext(
        session=session,
        settings=settings,
        client_factory=lambda: EBirdClient("test-key", BASE_URL, min_interval=0),
    )
    yield c
    c.close()


@pytest.fixture
def api(session: Session, settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)
