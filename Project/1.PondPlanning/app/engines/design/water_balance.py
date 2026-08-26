"""Daily water balance of the pond over the rainfall record → fill reliability.

``S[t+1] = min(C, S[t] + inflow - evaporation - seepage)``, spill = overflow.

- **Inflow** = daily SCS-CN runoff depth x catchment area x harvest
  efficiency (the share of catchment runoff that actually reaches the pond
  through channels and intake — 0.5-0.7 in practice; 0.6 is used and the
  bounds are reported).
- **Evaporation** = 0.7 x pan evaporation (the standard pan coefficient),
  with a monthly pan climatology for central India (IMD normals), over the
  current water surface.
- **Seepage** = a stated rate (2 mm/day; 1-3 typical for loams) over the wetted area.
- **Fill reliability** = fraction of years in which storage reaches >= 90 %
  of capacity at least once; months-with-water = months with storage above
  dead storage; spill = mean annual overflow.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.domain.rainfall import DailyRainfall
from app.engines.design.geometry import PondGeometry

FloatArray = NDArray[np.float64]

#: Mean pan evaporation, mm/day, by month — central India (IMD normals, approx.).
PAN_EVAPORATION_MM_DAY: tuple[float, ...] = (
    3.2,
    4.5,
    6.8,
    9.5,
    11.0,
    8.0,
    4.6,
    4.0,
    4.4,
    4.8,
    3.6,
    3.0,
)
PAN_COEFFICIENT = 0.7


@dataclass(frozen=True, slots=True)
class BalanceResult:
    """Reliability figures from the simulation."""

    years: int
    fill_reliability: float  # 0..1
    months_with_water_mean: float
    mean_annual_spill_m3: float
    mean_annual_evaporation_m3: float
    mean_annual_seepage_m3: float
    mean_annual_inflow_m3: float
    end_of_year_storage_mean_fraction: float


def simulate(
    record: DailyRainfall,
    daily_runoff_mm: FloatArray,
    catchment_area_m2: float,
    pond: PondGeometry,
    *,
    harvest_efficiency: float = 0.6,
    seepage_mm_day: float = 2.0,
    dead_storage_fraction: float = 0.15,
) -> BalanceResult:
    """Run the daily balance over every complete year of the record."""
    capacity = pond.storage_m3
    dead = dead_storage_fraction * capacity
    days = record.days
    years = days.astype("datetime64[Y]").astype(int) + 1970
    months = days.astype("datetime64[M]").astype(int) % 12
    inflow = (
        np.nan_to_num(daily_runoff_mm, nan=0.0) / 1000.0 * catchment_area_m2 * harvest_efficiency
    )

    storage = 0.0
    filled_years: set[int] = set()
    months_with_water: dict[int, set[int]] = {}
    spill: dict[int, float] = {}
    evap_total: dict[int, float] = {}
    seep_total: dict[int, float] = {}
    inflow_total: dict[int, float] = {}
    end_storage: dict[int, float] = {}
    for i in range(days.size):
        year, month = int(years[i]), int(months[i])
        # water level from storage: sqrt inversion of the frustum, adequate at daily steps
        level = pond.depth_m * (storage / capacity) ** 0.5 if capacity > 0 else 0.0
        surface = pond.area_at_level(level) if storage > 0 else 0.0
        evap = PAN_COEFFICIENT * PAN_EVAPORATION_MM_DAY[month] / 1000.0 * surface
        seep = seepage_mm_day / 1000.0 * surface
        storage = storage + inflow[i] - evap - seep
        if storage < 0:
            storage = 0.0
        overflow = max(storage - capacity, 0.0)
        storage -= overflow
        spill[year] = spill.get(year, 0.0) + overflow
        evap_total[year] = evap_total.get(year, 0.0) + evap
        seep_total[year] = seep_total.get(year, 0.0) + seep
        inflow_total[year] = inflow_total.get(year, 0.0) + inflow[i]
        if storage >= 0.9 * capacity:
            filled_years.add(year)
        if storage > dead:
            months_with_water.setdefault(year, set()).add(month)
        end_storage[year] = storage
    all_years = sorted(spill)
    n = len(all_years)
    if n == 0:
        return BalanceResult(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    return BalanceResult(
        years=n,
        fill_reliability=len(filled_years) / n,
        months_with_water_mean=float(
            np.mean([len(months_with_water.get(y, ())) for y in all_years])
        ),
        mean_annual_spill_m3=float(np.mean([spill[y] for y in all_years])),
        mean_annual_evaporation_m3=float(np.mean([evap_total[y] for y in all_years])),
        mean_annual_seepage_m3=float(np.mean([seep_total[y] for y in all_years])),
        mean_annual_inflow_m3=float(np.mean([inflow_total[y] for y in all_years])),
        end_of_year_storage_mean_fraction=float(
            np.mean([end_storage[y] for y in all_years]) / capacity if capacity else 0.0
        ),
    )
