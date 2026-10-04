"""Golden tests for the pond-design engines: geometry, optimiser, water balance, spillway, EAV."""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from app.domain.geo import GridSpec
from app.domain.rainfall import DailyRainfall
from app.domain.raster import Raster
from app.engines.design.eav import eav_curve
from app.engines.design.geometry import PondGeometry, solve_top_dimensions
from app.engines.design.optimiser import optimise
from app.engines.design.spillway import size_spillway
from app.engines.design.water_balance import simulate
from app.engines.hydrology.conditioning import fill_depressions
from app.engines.hydrology.flow import build_flow_model

pytestmark = pytest.mark.golden


def test_frustum_matches_the_hand_calculation() -> None:
    """Top 40x20, depth 2, slope 2:1 -> bottom 32x12; V = 2/3 (800 + 384 + sqrt(800*384))."""
    g = PondGeometry(
        depth_m=2.0, top_length_m=40.0, top_width_m=20.0, side_slope=2.0, freeboard_m=0.5
    )
    assert g.bottom_length_m == 32.0 and g.bottom_width_m == 12.0
    expected = 2.0 / 3.0 * (800 + 384 + math.sqrt(800 * 384))
    assert g.storage_m3 == pytest.approx(expected)
    assert g.volume_at_level(2.0) == pytest.approx(expected)
    assert g.volume_at_level(0.0) == 0.0 and g.area_at_level(0.0) == 384.0
    assert g.excavation_m3 > g.storage_m3, "the freeboard band is cut but not stored"
    assert g.feasible


def test_solve_top_dimensions_hits_the_target() -> None:
    dims = solve_top_dimensions(10_000.0, 2.5, 1.5, 2.0)
    assert dims is not None
    length, width = dims
    assert length == pytest.approx(1.5 * width)
    assert PondGeometry(2.5, length, width, 2.0, 0.5).storage_m3 == pytest.approx(
        10_000.0, rel=1e-6
    )
    assert solve_top_dimensions(1.0, 3.5, 1.0, 2.0) is None, "too small to have a 5 m floor"


def test_optimiser_picks_a_feasible_minimum_cost_design_and_respects_max_depth() -> None:
    best, candidates = optimise(20_000.0)
    assert best.geometry.storage_m3 == pytest.approx(20_000.0, rel=1e-6)
    assert all(c.cost_inr >= best.cost_inr - 1 for c in candidates)
    assert 1.5 <= best.geometry.depth_m <= 3.5
    shallow, _ = optimise(20_000.0, max_depth_m=2.0)
    assert shallow.geometry.depth_m <= 2.0
    with pytest.raises(ValueError, match="no feasible"):
        optimise(10.0)


def monsoon_record(
    years: int, daily_runoff_mm: float, days_per_year: int = 40
) -> tuple[DailyRainfall, np.ndarray]:
    days = np.arange(np.datetime64("2000-01-01"), np.datetime64(f"{2000 + years}-01-01"))
    months = days.astype("datetime64[M]").astype(int) % 12 + 1
    dom = (days - days.astype("datetime64[M]")).astype(int) + 1
    rain = np.zeros(days.size)
    rain[(months == 7) & (dom <= days_per_year // 2)] = 40.0
    rain[(months == 8) & (dom <= days_per_year // 2)] = 40.0
    runoff = np.where(rain > 0, daily_runoff_mm, 0.0)
    return DailyRainfall(days, rain, "synthetic", "c", 21.0, 81.0, "n"), runoff


def test_water_balance_fills_a_small_pond_every_year_and_never_a_huge_one() -> None:
    record, runoff = monsoon_record(5, daily_runoff_mm=10.0)  # 400 mm/yr runoff
    area = 20e4  # 20 ha → 80 000 m³ runoff → 48 000 m³ inflow at 0.6
    small = PondGeometry(2.0, 60.0, 40.0, 2.0, 0.5)  # ~3 500 m³
    result = simulate(record, runoff, area, small)
    assert result.years == 5 and result.fill_reliability == 1.0
    assert result.mean_annual_spill_m3 > 0.9 * (48_000 - small.storage_m3) * 0.8
    assert 0 < result.months_with_water_mean <= 12
    huge = PondGeometry(3.5, 400.0, 400.0, 2.0, 0.5)  # ~500 000 m³
    assert simulate(record, runoff, area, huge).fill_reliability == 0.0


def test_spillway_scales_with_area_and_rainfall() -> None:
    a = size_spillway(
        rainfall_25y_1day_mm=200,
        longest_flow_path_m=1500,
        mean_slope_ratio=0.01,
        catchment_area_m2=50e4,
        runoff_coefficient=0.4,
    )
    b = size_spillway(
        rainfall_25y_1day_mm=200,
        longest_flow_path_m=1500,
        mean_slope_ratio=0.01,
        catchment_area_m2=100e4,
        runoff_coefficient=0.4,
    )
    c = size_spillway(
        rainfall_25y_1day_mm=300,
        longest_flow_path_m=1500,
        mean_slope_ratio=0.01,
        catchment_area_m2=50e4,
        runoff_coefficient=0.4,
    )
    assert b.peak_flow_m3_s == pytest.approx(2 * a.peak_flow_m3_s)
    assert c.peak_flow_m3_s > a.peak_flow_m3_s
    assert a.weir_length_m >= 1.0 and a.time_of_concentration_min > 0
    assert a.weir_length_m == pytest.approx(a.peak_flow_m3_s / (1.7 * 0.3**1.5))


def test_eav_curve_of_a_bowl_grows_monotonically_and_matches_geometry() -> None:
    grid = GridSpec(32644, 0.0, 1000.0, 10.0, 41, 41)
    cc, rr = np.meshgrid(np.arange(41), np.arange(41))
    r = np.hypot((cc - 20) * 10, (rr - 20) * 10)
    # a bowl with an outlet channel to the south edge so it is not filled by conditioning
    z = 100.0 + 0.02 * r
    z[21:, 20] = np.minimum(z[21:, 20], 99.0 - 0.01 * np.arange(1, 21))
    dem = Raster(grid, z)
    model = build_flow_model(fill_depressions(dem).filled)
    curve = eav_curve(model, 20, 20, max_rise_m=2.0, step_m=0.5)
    volumes = [p.volume_m3 for p in curve]
    areas = [p.area_m2 for p in curve]
    assert volumes[0] == 0.0 and areas[0] == 0.0
    assert all(b >= a for a, b in itertools.pairwise(volumes))
    assert all(b >= a for a, b in itertools.pairwise(areas))
    # a 1 m rise on a 2 % cone floods r < 50 m → π·50² ≈ 7 854 m²; cells of 100 m²
    one_metre = curve[2]
    assert one_metre.area_m2 == pytest.approx(math.pi * 50**2, rel=0.2)
