"""Thin, typed client for the eBird API 2.0 (https://documenter.getpostman.com/view/664302/S1ENwy59).

Each method returns (raw_json, parsed_models) so callers can archive the raw payload
before transforming it.
"""

import logging
from datetime import date
from typing import Any

import httpx
from sqlalchemy import Engine
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.ebird.rate_limit import request_slot
from app.ebird.schemas import EBirdDailyStats, EBirdObservation, EBirdTaxon

log = logging.getLogger(__name__)


class EBirdError(RuntimeError):
    pass


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


class EBirdClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.ebird.org/v2",
        min_interval: float = 1.1,
        transport: httpx.BaseTransport | None = None,
        engine: Engine | None = None,
    ) -> None:
        if not api_key:
            raise EBirdError("EBIRD_API_KEY is not set")
        self._http = httpx.Client(
            base_url=base_url,
            headers={"X-eBirdApiToken": api_key},
            timeout=30.0,
            transport=transport,
        )
        self._min_interval = min_interval
        self._engine = engine

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "EBirdClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- low level -------------------------------------------------------------------

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        # Retries re-enter here, so they wait for a slot like any other request.
        with request_slot(self._min_interval, self._engine):
            log.debug("GET %s %s", path, params)
            resp = self._http.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    # --- endpoints -------------------------------------------------------------------

    def recent_observations(self, region: str, back: int = 1) -> tuple[Any, list[EBirdObservation]]:
        """Most recent sighting of each species in the region over the last `back` days."""
        raw = self.get(f"/data/obs/{region}/recent", {"back": back})
        return raw, [EBirdObservation.model_validate(o) for o in raw]

    def historic_observations(self, region: str, day: date) -> tuple[Any, list[EBirdObservation]]:
        """Every species reported in the region on `day` (one record per species)."""
        raw = self.get(f"/data/obs/{region}/historic/{day.year}/{day.month}/{day.day}")
        return raw, [EBirdObservation.model_validate(o) for o in raw]

    def daily_stats(self, region: str, day: date) -> tuple[Any, EBirdDailyStats]:
        raw = self.get(f"/product/stats/{region}/{day.year}/{day.month}/{day.day}")
        return raw, EBirdDailyStats.model_validate(raw)

    def taxonomy(self) -> tuple[Any, list[EBirdTaxon]]:
        raw = self.get("/ref/taxonomy/ebird", {"fmt": "json"})
        return raw, [EBirdTaxon.model_validate(t) for t in raw]
