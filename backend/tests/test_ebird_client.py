from datetime import date, datetime

import httpx
import pytest
import respx
from tenacity import wait_none

from app.ebird import EBirdClient, EBirdError
from tests.conftest import BASE_URL, REGION, load_fixture


@pytest.fixture
def client():
    with EBirdClient("test-key", BASE_URL, min_interval=0) as c:
        yield c


@pytest.fixture(autouse=True)
def _no_retry_wait(monkeypatch):
    monkeypatch.setattr(EBirdClient.get.retry, "wait", wait_none())


def test_requires_api_key():
    with pytest.raises(EBirdError):
        EBirdClient("")


@respx.mock(base_url=BASE_URL)
def test_historic_observations_parses_and_sends_token(respx_mock, client):
    route = respx_mock.get(f"/data/obs/{REGION}/historic/2026/11/18").respond(
        json=load_fixture("historic_day.json")
    )
    raw, obs = client.historic_observations(REGION, date(2026, 11, 18))

    assert route.calls.last.request.headers["X-eBirdApiToken"] == "test-key"
    assert len(raw) == 3
    assert obs[0].species_code == "amecro"
    assert obs[0].obs_dt == datetime(2026, 11, 18, 8, 15)
    # Date-only obsDt values are accepted
    assert obs[2].obs_date == date(2026, 11, 18)
    assert obs[2].how_many is None


@respx.mock(base_url=BASE_URL)
def test_retries_on_server_error(respx_mock, client):
    route = respx_mock.get(f"/product/stats/{REGION}/2026/11/18").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json=load_fixture("daily_stats.json")),
        ]
    )
    _, stats = client.daily_stats(REGION, date(2026, 11, 18))
    assert route.call_count == 2
    assert stats.num_checklists == 42


@respx.mock(base_url=BASE_URL)
def test_does_not_retry_client_errors(respx_mock, client):
    route = respx_mock.get(f"/data/obs/{REGION}/recent").respond(403)
    with pytest.raises(httpx.HTTPStatusError):
        client.recent_observations(REGION)
    assert route.call_count == 1
