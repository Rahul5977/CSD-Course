"""Rainfall use case: fetch the record for a point, compute statistics, shape the response."""

from __future__ import annotations

from datetime import date

from app.domain.rainfall import DailyRainfall
from app.domain.units import Quantity, Unit
from app.engines.rainfall.statistics import RainfallStats, compute_statistics
from app.providers.resilience import FallbackChain
from app.schemas.common import QuantityOut, ResultWarning
from app.schemas.rainfall import MonthlyNormal, RainfallDaily, RainfallSeries, RainfallStatistics

#: ERA5-Land reanalysis vs gauge: roughly ±15 % on annual totals in central India.
ANNUAL_UNCERTAINTY_PCT = 15.0


def record_window(years: int, today: date | None = None) -> tuple[date, date]:
    """The last ``years`` complete calendar years ending last year."""
    today = today or date.today()
    end = date(today.year - 1, 12, 31)
    start = date(end.year - years + 1, 1, 1)
    return start, end


def fetch_record(chain: FallbackChain, lon: float, lat: float, years: int) -> DailyRainfall:
    """Daily record for the standard window."""
    start, end = record_window(years)
    return chain.daily(lon, lat, start, end)


def _fallback_label(chain: FallbackChain, record: DailyRainfall) -> str:
    if not record.fetched_live:
        return "cache"
    if chain.last_used and chain.last_used != "open_meteo_era5_land":
        return "secondary_provider"
    return "none"


def statistics_response(chain: FallbackChain, record: DailyRainfall) -> RainfallStatistics:
    """Compute and project the FR5 statistics."""
    stats: RainfallStats = compute_statistics(record)
    q = QuantityOut.from_domain
    u = ANNUAL_UNCERTAINTY_PCT
    warnings: list[ResultWarning] = []
    if stats.completeness_pct < 98:
        warnings.append(
            ResultWarning(
                code="incomplete_record",
                message=f"{100 - stats.completeness_pct:.1f} % of days are missing; incomplete "
                "years were excluded rather than scaled.",
                severity="caution",
            )
        )
    if not record.fetched_live:
        warnings.append(
            ResultWarning(
                code="stale_data",
                message="The live rainfall API was unreachable; these figures come from the "
                "cached record.",
                severity="caution",
            )
        )
    if stats.years < 20:
        warnings.append(
            ResultWarning(
                code="short_record",
                message=f"Only {stats.years} complete years; dependable rainfall is less certain "
                "than with the 20+ years practice recommends.",
                severity="caution",
            )
        )
    return RainfallStatistics(
        source=record.source,
        years_of_record=stats.years,
        start_year=stats.start_year,
        end_year=stats.end_year,
        mean_annual=q(
            Quantity(
                stats.mean_annual_mm,
                Unit.MILLIMETRE_PER_YEAR,
                u,
                "arithmetic mean of complete calendar years",
            )
        ),
        median_annual=q(
            Quantity(
                stats.median_annual_mm,
                Unit.MILLIMETRE_PER_YEAR,
                u,
                "50th percentile of annual totals",
            )
        ),
        dependable_75=q(
            Quantity(
                stats.dependable_75_mm,
                Unit.MILLIMETRE_PER_YEAR,
                u,
                f"75 % dependable - Weibull plotting position m/(n+1) on {stats.years} "
                "annual totals",
            )
        ),
        coefficient_of_variation=q(
            Quantity(stats.cv_pct, Unit.PERCENT, None, "sigma / mu of annual totals")
        ),
        monsoon_share=q(
            Quantity(
                stats.monsoon_share_pct, Unit.PERCENT, 3.0, "Jun-Sep share of the annual total"
            )
        ),
        max_daily_recorded=q(
            Quantity(
                stats.max_daily_mm,
                Unit.MILLIMETRE,
                20.0,
                f"highest single day in the record ({stats.max_daily_date})",
            )
        ),
        rainy_days_mean=q(
            Quantity(
                stats.rainy_days_mean, Unit.COUNT, 10.0, "mean days per year with >= 2.5 mm (IMD)"
            )
        ),
        monthly_normals=[
            MonthlyNormal(
                month=row.month,
                mean_rainfall=q(Quantity(row.mean_mm, Unit.MILLIMETRE, u, "monthly mean")),
                rainy_days=q(Quantity(row.rainy_days, Unit.COUNT, 10.0, "mean per month")),
            )
            for row in stats.monthly
        ],
        data_completeness=q(
            Quantity(stats.completeness_pct, Unit.PERCENT, None, "days with a value")
        ),
        fallback_used=_fallback_label(chain, record),  # type: ignore[arg-type]
        attribution=record.attribution,
        warnings=warnings,
    )


def series_response(record: DailyRainfall, chain: FallbackChain) -> RainfallSeries:
    """Project the daily record onto the wire."""
    q = QuantityOut.from_domain
    return RainfallSeries(
        source=record.source,
        station_or_grid=record.grid_label,
        latitude=record.latitude,
        longitude=record.longitude,
        start=record.start,
        end=record.end,
        days=int(record.days.size),
        series=[
            RainfallDaily(
                day=day.astype("datetime64[D]").astype(date),
                rainfall=q(Quantity(float(mm), Unit.MILLIMETRE, None, None)),
            )
            for day, mm in zip(record.days, record.mm, strict=True)
            if mm == mm  # skip NaN days
        ],
        warnings=(
            []
            if record.fetched_live
            else [ResultWarning(code="stale_data", message="served from cache", severity="caution")]
        ),
    )
