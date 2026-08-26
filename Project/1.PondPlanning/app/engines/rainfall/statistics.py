"""Rainfall statistics from a daily record (FR5).

All from the daily series, so nothing here is a raw dump:

- **Annual totals** by calendar year (complete years only), their mean,
  median, standard deviation and coefficient of variation.
- **75 % dependable rainfall** — the annual total equalled or exceeded in
  three years out of four — by the **Weibull plotting position**
  ``P = m / (n + 1)`` on the ranked totals, interpolated at P = 0.75. This is
  the design figure in Indian minor-irrigation practice; designing to the
  mean produces a pond that fails roughly every second year.
- **Monsoon share** (June-September), the IMD **rainy-day** definition
  (≥ 2.5 mm), **max 1-day** rainfall, and **monthly normals**.
- **25-year 1-day rainfall** by a **Gumbel (EV1)** fit, method of moments,
  on the annual maxima — the depth the spillway is sized for in P3.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.domain.errors import ValidationError
from app.domain.rainfall import DailyRainfall

FloatArray = NDArray[np.float64]

RAINY_DAY_MM = 2.5  # India Meteorological Department definition
MONSOON_MONTHS = (6, 7, 8, 9)  # JJAS


@dataclass(frozen=True, slots=True)
class MonthlyNormalRow:
    """Long-term mean for one calendar month."""

    month: int
    mean_mm: float
    rainy_days: float


@dataclass(frozen=True, slots=True)
class RainfallStats:
    """Everything the FR5 card and the runoff engine need."""

    years: int
    start_year: int
    end_year: int
    annual_totals: dict[int, float]
    mean_annual_mm: float
    median_annual_mm: float
    std_annual_mm: float
    cv_pct: float
    dependable_75_mm: float
    dependable_50_mm: float
    monsoon_share_pct: float
    rainy_days_mean: float
    max_daily_mm: float
    max_daily_date: str
    return_period_25y_1day_mm: float
    gumbel_location: float
    gumbel_scale: float
    monthly: list[MonthlyNormalRow]
    completeness_pct: float


def _years_months(days: NDArray[np.datetime64]) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    years = days.astype("datetime64[Y]").astype(int) + 1970
    months = days.astype("datetime64[M]").astype(int) % 12 + 1
    return years.astype(np.int64), months.astype(np.int64)


def weibull_dependable(annual: FloatArray, probability: float) -> float:
    """Annual total exceeded with the given probability (Weibull m/(n+1), interpolated)."""
    ranked = np.sort(annual)[::-1]  # descending: rank 1 = wettest
    n = ranked.size
    if n == 0:
        msg = "no complete years in the record"
        raise ValidationError(msg)
    exceedance = np.arange(1, n + 1) / (n + 1)
    return float(np.interp(probability, exceedance, ranked))


def gumbel_return_level(
    maxima: FloatArray, return_period_years: float
) -> tuple[float, float, float]:
    """Gumbel EV1 by method of moments: returns (level, location u, scale alpha)."""
    if maxima.size < 3:
        return float(np.max(maxima)), float(np.mean(maxima)), 0.0
    mean, std = float(np.mean(maxima)), float(np.std(maxima, ddof=1))
    alpha = std * np.sqrt(6.0) / np.pi
    u = mean - 0.5772156649 * alpha
    y = -np.log(-np.log(1.0 - 1.0 / return_period_years))
    return float(u + alpha * y), float(u), float(alpha)


def compute_statistics(record: DailyRainfall, *, min_days_per_year: int = 350) -> RainfallStats:
    """Derive the full statistics set from a daily record."""
    years, months = _years_months(record.days)
    mm = record.mm
    valid = ~np.isnan(mm)
    totals: dict[int, float] = {}
    rainy: dict[int, int] = {}
    maxima: dict[int, float] = {}
    monsoon: dict[int, float] = {}
    for year in np.unique(years):
        sel = (years == year) & valid
        if sel.sum() < min_days_per_year:
            continue  # incomplete year: excluded rather than scaled up
        vals = mm[sel]
        totals[int(year)] = float(vals.sum())
        rainy[int(year)] = int((vals >= RAINY_DAY_MM).sum())
        maxima[int(year)] = float(vals.max())
        monsoon[int(year)] = float(mm[sel & np.isin(months, MONSOON_MONTHS)].sum())
    if not totals:
        msg = "no complete calendar year in the rainfall record"
        raise ValidationError(msg, {"days": int(record.days.size)})

    annual = np.array(list(totals.values()), dtype=np.float64)
    level, u, alpha = gumbel_return_level(np.array(list(maxima.values())), 25.0)
    peak_index = int(np.nanargmax(mm))
    monthly = [
        MonthlyNormalRow(
            month=int(m),
            mean_mm=float(np.nansum(mm[(months == m)]) / len(totals)),
            rainy_days=float(((mm >= RAINY_DAY_MM) & (months == m)).sum() / len(totals)),
        )
        for m in range(1, 13)
    ]
    return RainfallStats(
        years=len(totals),
        start_year=min(totals),
        end_year=max(totals),
        annual_totals=totals,
        mean_annual_mm=float(annual.mean()),
        median_annual_mm=float(np.median(annual)),
        std_annual_mm=float(annual.std(ddof=1)) if annual.size > 1 else 0.0,
        cv_pct=float(100.0 * annual.std(ddof=1) / annual.mean()) if annual.size > 1 else 0.0,
        dependable_75_mm=weibull_dependable(annual, 0.75),
        dependable_50_mm=weibull_dependable(annual, 0.50),
        monsoon_share_pct=float(100.0 * sum(monsoon.values()) / sum(totals.values())),
        rainy_days_mean=float(np.mean(list(rainy.values()))),
        max_daily_mm=float(mm[peak_index]),
        max_daily_date=str(record.days[peak_index].astype("datetime64[D]")),
        return_period_25y_1day_mm=level,
        gumbel_location=u,
        gumbel_scale=alpha,
        monthly=monthly,
        completeness_pct=100.0 * record.completeness,
    )
