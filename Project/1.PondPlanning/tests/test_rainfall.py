"""Rainfall: statistics golden tests, recorded-response parsers, resilience decorators."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.domain.errors import UpstreamUnavailableError
from app.domain.rainfall import DailyRainfall
from app.engines.rainfall.statistics import (
    compute_statistics,
    gumbel_return_level,
    weibull_dependable,
)
from app.providers.rainfall.adapters import RecordedAdapter, parse_nasa_power, parse_open_meteo
from app.providers.resilience import Cached, CircuitBreaker, FallbackChain, Retry
from app.providers.storage import LocalObjectStore

FIXTURES = Path(__file__).parent / "fixtures"
OPEN_METEO = FIXTURES / "open_meteo_khapri_1981_2025.json"
NASA = FIXTURES / "nasa_power_khapri_2020.json"


def synthetic_record(years: int = 10, annual_mm: float = 1000.0) -> DailyRainfall:
    """Exactly ``annual_mm`` per year, all of it in July, 20 rainy days of 50 mm."""
    days = np.arange(np.datetime64("2000-01-01"), np.datetime64(f"{2000 + years}-01-01"))
    mm = np.zeros(days.size)
    months = days.astype("datetime64[M]").astype(int) % 12 + 1
    dom = (days - days.astype("datetime64[M]")).astype(int) + 1
    mm[(months == 7) & (dom <= 20)] = annual_mm / 20
    return DailyRainfall(days, mm, "synthetic", "cell", 21.0, 81.0, "none")


def test_statistics_on_a_synthetic_record_are_exact() -> None:
    stats = compute_statistics(synthetic_record())
    assert stats.years == 10 and stats.start_year == 2000 and stats.end_year == 2009
    assert stats.mean_annual_mm == pytest.approx(1000.0)
    assert stats.dependable_75_mm == pytest.approx(1000.0)
    assert stats.cv_pct == pytest.approx(0.0)
    assert stats.monsoon_share_pct == pytest.approx(100.0)
    assert stats.rainy_days_mean == pytest.approx(20.0)
    assert stats.max_daily_mm == pytest.approx(50.0)
    assert stats.monthly[6].mean_mm == pytest.approx(1000.0) and stats.monthly[0].mean_mm == 0.0
    assert stats.completeness_pct == 100.0


def test_weibull_dependable_interpolates_the_ranked_totals() -> None:
    annual = np.array([800.0, 900.0, 1000.0, 1100.0, 1200.0, 1300.0, 1400.0])
    # n=7: exceedance 1/8..7/8; 0.75 lies between ranks 5 (5/8) and 6 (6/8) → 1000..900
    assert weibull_dependable(annual, 0.75) == pytest.approx(900.0)
    assert weibull_dependable(annual, 0.5) == pytest.approx(1100.0)


def test_gumbel_return_level_grows_with_the_return_period() -> None:
    maxima = np.array([60.0, 80.0, 95.0, 110.0, 70.0, 130.0, 90.0, 85.0, 100.0, 75.0])
    t25, u, alpha = gumbel_return_level(maxima, 25.0)
    t100, _, _ = gumbel_return_level(maxima, 100.0)
    assert alpha > 0 and u < np.mean(maxima)
    assert np.max(maxima) < t25 < t100 < 300


def test_incomplete_years_are_excluded_not_scaled() -> None:
    rec = synthetic_record(3)
    mm = rec.mm.copy()
    days = rec.days
    years = days.astype("datetime64[Y]").astype(int) + 1970
    mm[(years == 2001)] = np.nan  # a whole missing year
    mm[(years == 2002)][:30] = np.nan
    stats = compute_statistics(DailyRainfall(days, mm, "s", "c", 21.0, 81.0, "n"))
    assert stats.years == 2 and 2001 not in stats.annual_totals
    assert stats.completeness_pct < 100


@pytest.mark.skipif(not OPEN_METEO.exists(), reason="recorded fixture missing")
def test_recorded_open_meteo_parses_and_looks_like_chhattisgarh() -> None:
    record = parse_open_meteo(json.loads(OPEN_METEO.read_text()), 81.297, 21.2517)
    assert record.days.size == 16436 and record.completeness == 1.0
    stats = compute_statistics(record)
    assert stats.years == 45
    assert 900 < stats.mean_annual_mm < 1700, stats.mean_annual_mm
    assert stats.dependable_75_mm < stats.median_annual_mm < stats.mean_annual_mm * 1.05
    assert stats.monsoon_share_pct > 75, "central India: the monsoon is most of the year"
    assert 40 < stats.rainy_days_mean < 120
    maxima = stats.max_daily_mm
    # The record holds one extreme day (~370 mm); a 25-year Gumbel estimate must
    # sit above the typical annual maximum but is not obliged to chase the outlier.
    assert 100 < stats.return_period_25y_1day_mm < maxima


@pytest.mark.skipif(not NASA.exists(), reason="recorded fixture missing")
def test_recorded_nasa_power_parses() -> None:
    record = parse_nasa_power(json.loads(NASA.read_text()), 81.297, 21.2517)
    assert record.days.size == 366 and record.start == date(2020, 1, 1)
    assert 600 < float(np.nansum(record.mm)) < 2500


@pytest.mark.skipif(not OPEN_METEO.exists(), reason="recorded fixture missing")
def test_recorded_adapter_slices_and_refuses_other_places() -> None:
    adapter = RecordedAdapter(OPEN_METEO)
    rec = adapter.daily(81.297, 21.2517, date(1995, 1, 1), date(2004, 12, 31))
    assert rec.start == date(1995, 1, 1) and rec.end == date(2004, 12, 31)
    assert rec.fetched_live is False
    with pytest.raises(UpstreamUnavailableError):
        adapter.daily(77.2, 28.6, date(1995, 1, 1), date(2004, 12, 31))


class Flaky:
    """A provider that fails ``n`` times, then answers."""

    name = "flaky"

    def __init__(self, failures: int) -> None:
        """Fail the first ``failures`` calls."""
        self.failures = failures
        self.calls = 0

    def daily(self, lon: float, lat: float, start: date, end: date) -> DailyRainfall:
        """Raise until the failure budget is spent, then return a synthetic record."""
        self.calls += 1
        if self.calls <= self.failures:
            msg = "boom"
            raise UpstreamUnavailableError(msg)
        return synthetic_record(2)


def test_retry_recovers_from_transient_failures_without_sleeping_for_real() -> None:
    naps: list[float] = []
    provider = Retry(Flaky(2), attempts=3, sleep=naps.append)
    assert provider.daily(0, 0, date(2000, 1, 1), date(2001, 12, 31)).days.size > 0
    assert len(naps) == 2
    with pytest.raises(UpstreamUnavailableError):
        Retry(Flaky(5), attempts=3, sleep=naps.append).daily(
            0, 0, date(2000, 1, 1), date(2001, 12, 31)
        )


def test_circuit_breaker_opens_then_half_opens() -> None:
    clock = [0.0]
    flaky = Flaky(3)
    breaker = CircuitBreaker(flaky, failures=3, reset_s=100.0, clock=lambda: clock[0])
    for _ in range(3):
        with pytest.raises(UpstreamUnavailableError):
            breaker.daily(0, 0, date(2000, 1, 1), date(2001, 12, 31))
    assert breaker.is_open
    with pytest.raises(UpstreamUnavailableError):  # short-circuited: the provider is not called
        breaker.daily(0, 0, date(2000, 1, 1), date(2001, 12, 31))
    assert flaky.calls == 3 and breaker.state.stats["short_circuited"] == 1
    clock[0] = 200.0  # window elapsed → half-open trial succeeds and closes the breaker
    assert breaker.daily(0, 0, date(2000, 1, 1), date(2001, 12, 31)).days.size > 0
    assert not breaker.is_open and breaker.state.failures == 0


def test_cache_serves_stale_data_when_the_provider_is_down(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)
    good = Flaky(0)
    cached = Cached(good, store, ttl_s=0.0)  # ttl 0: every call tries live first
    first = cached.daily(0, 0, date(2000, 1, 1), date(2001, 12, 31))
    assert first.fetched_live is True and good.calls == 1
    fresh = Cached(Flaky(99), store, ttl_s=3600.0)  # fresh entry: no live call, still "live" data
    assert fresh.daily(0, 0, date(2000, 1, 1), date(2001, 12, 31)).fetched_live is True
    dead = Cached(Flaky(99), store, ttl_s=0.0)
    stale = dead.daily(0, 0, date(2000, 1, 1), date(2001, 12, 31))
    assert stale.fetched_live is False and np.allclose(stale.mm, first.mm)


def test_fallback_chain_records_which_provider_answered() -> None:
    dead, alive = Flaky(99), Flaky(0)
    alive.name = "alive"
    chain = FallbackChain([dead, alive])
    chain.daily(0, 0, date(2000, 1, 1), date(2001, 12, 31))
    assert chain.last_used == "alive" and chain.last_errors == ["flaky: boom"]
    with pytest.raises(UpstreamUnavailableError):
        FallbackChain([Flaky(99)]).daily(0, 0, date(2000, 1, 1), date(2001, 12, 31))


@pytest.mark.skipif(not OPEN_METEO.exists(), reason="recorded fixture missing")
def test_rainfall_routes_are_real_and_labelled_honestly(client: TestClient) -> None:
    response = client.get("/api/v1/rainfall/statistics?lon=81.297&lat=21.2517&years=30")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "X-Fixture-Data" not in response.headers
    assert body["years_of_record"] == 30 and body["fallback_used"] == "cache"
    assert (
        body["dependable_75"]["unit"] == "mm/yr" and body["dependable_75"]["uncertainty_pct"] == 15
    )
    assert len(body["monthly_normals"]) == 12
    assert any(w["code"] == "stale_data" for w in body["warnings"])
    series = client.get(
        "/api/v1/rainfall/series?lon=81.297&lat=21.2517&start=2019-06-01&end=2019-06-30"
    ).json()
    assert series["days"] == 30 and series["series"][0]["day"] == "2019-06-01"
    # a point the recorded fixture does not cover → 503 problem document
    far = client.get("/api/v1/rainfall/statistics?lon=77.2&lat=28.6")
    assert far.status_code == 503 and far.json()["code"] == "upstream_unavailable"
