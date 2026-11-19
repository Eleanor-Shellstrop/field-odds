from datetime import date, datetime, timedelta

import pytest

from app.ml.frequency import FrequencyModel, compute_likelihoods, sample_days
from app.models import DailyStats, Observation, Species
from tests.conftest import REGION

TARGET = date(2026, 11, 19)


def test_sample_days_covers_seasonal_windows_and_recent_days():
    days = sample_days(TARGET, years=3, window_days=7, recent_days=14, recent_weight=2.0)
    assert len(days) == 3 * 15 + 14
    assert days[date(2025, 11, 19)] == 1.0
    assert days[date(2023, 11, 12)] == 1.0
    assert days[TARGET - timedelta(days=1)] == 2.0
    assert TARGET not in days  # today isn't in yet


def test_sample_days_handles_leap_day():
    days = sample_days(date(2028, 2, 29), years=1, window_days=0, recent_days=0, recent_weight=1)
    assert list(days) == [date(2027, 2, 28)]


def test_compute_likelihoods_weights_and_ignores_days_without_effort():
    d1, d2, d3, no_effort = (date(2026, 1, i) for i in (1, 2, 3, 4))
    weights = {d1: 1.0, d2: 1.0, d3: 2.0, no_effort: 1.0}
    effort = {d1, d2, d3}
    detections = {"amecro": {d1, d2, d3}, "baleag": {d3}, "rarebird": {no_effort}}

    result = {
        r.species_code: r.likelihood for r in compute_likelihoods(weights, effort, detections)
    }

    assert result["amecro"] == pytest.approx(1.0)
    assert result["baleag"] == pytest.approx(2.0 / 4.0)
    assert "rarebird" not in result  # only seen on a day that doesn't count


def test_compute_likelihoods_empty_when_no_effort():
    assert compute_likelihoods({date(2026, 1, 1): 1.0}, set(), {"amecro": set()}) == []


def _obs(code: str, day: date, sub: str) -> Observation:
    return Observation(
        region_code=REGION,
        species_code=code,
        common_name=code,
        sci_name=code,
        sub_id=sub,
        obs_date=day,
        obs_dt=datetime.combine(day, datetime.min.time()),
        source="historic",
    )


def test_model_predict_against_db(session):
    model = FrequencyModel(years=1, window_days=1, recent_days=0)
    season = [date(2025, 11, 18), date(2025, 11, 19), date(2025, 11, 20)]
    session.add_all(
        DailyStats(region_code=REGION, day=d, num_checklists=5, num_contributors=3, num_species=40)
        for d in season
    )
    session.add(
        Species(
            species_code="gulls", common_name="gull sp.", sci_name="Larinae sp.", category="spuh"
        )
    )
    session.add_all(
        [
            _obs("amecro", season[0], "S1"),
            _obs("amecro", season[1], "S2"),
            _obs("baleag", season[2], "S3"),
            _obs("gulls", season[2], "S3"),
            _obs("amecro", date(2025, 6, 1), "S4"),  # out of window
        ]
    )
    session.commit()

    result = {r.species_code: r.likelihood for r in model.predict(session, REGION, TARGET)}

    assert result == {"amecro": pytest.approx(2 / 3), "baleag": pytest.approx(1 / 3)}
