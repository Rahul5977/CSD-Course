"""Golden tests for curve numbers and the three runoff methods."""

from __future__ import annotations

import numpy as np
import pytest

from app.domain.rainfall import DailyRainfall
from app.engines.runoff.curve_number import (
    CN_TABLE,
    amc_adjust,
    composite_curve_number,
    hsg_from_texture,
)
from app.engines.runoff.methods import RationalMethod, SCSCNMethod, StrangeMethod

pytestmark = pytest.mark.golden


def record_with(daily_values: list[float], year: int = 2001) -> DailyRainfall:
    """A complete year with the given values on its first days, zero elsewhere."""
    days = np.arange(np.datetime64(f"{year}-01-01"), np.datetime64(f"{year + 1}-01-01"))
    mm = np.zeros(days.size)
    mm[: len(daily_values)] = daily_values
    return DailyRainfall(days, mm, "synthetic", "cell", 21.0, 81.0, "none")


def test_hsg_rule_of_thumb() -> None:
    assert hsg_from_texture(clay_pct=8, sand_pct=80) == "A"
    assert hsg_from_texture(clay_pct=20, sand_pct=40) == "B"
    assert hsg_from_texture(clay_pct=30, sand_pct=40) == "C"
    assert hsg_from_texture(clay_pct=45, sand_pct=20) == "D"


def test_composite_cn_is_area_weighted_and_amc_adjusts_both_ways() -> None:
    land = np.array([[40, 40, 40], [30, 30, 80]], dtype=np.uint8)  # 3 crop, 2 grass, 1 water
    cn = composite_curve_number(land, "C")
    expected = (3 * CN_TABLE[40]["C"] + 2 * CN_TABLE[30]["C"] + 1 * CN_TABLE[80]["C"]) / 6
    assert cn.cn == pytest.approx(expected)
    assert cn.class_fractions[40] == pytest.approx(0.5)
    assert amc_adjust(80, "I") < 80 < amc_adjust(80, "III")
    assert cn.potential_retention_mm == pytest.approx(25400 / expected - 254)


def test_scs_cn_hand_calculation_and_daily_vs_annual_bias() -> None:
    """CN 80: S = 63.5 mm, Ia = 12.7 mm. A 50 mm day gives Q = 37.3² / (37.3 + 63.5) = 13.8 mm."""
    cn = composite_curve_number(np.array([[40]]), "B")  # CN 81 for cropland on B... use explicit
    from app.engines.runoff.curve_number import CurveNumber

    cn80 = CurveNumber(80.0, "C", "II")
    method = SCSCNMethod(cn80)
    one_day = method.annual(record_with([50.0]))
    assert one_day.runoff_mm[0] == pytest.approx(37.3**2 / (37.3 + 63.5), abs=0.05)
    # Twenty 50 mm days versus one 1000 mm "annual" storm: the annual-total
    # shortcut overestimates runoff by more than 3x for this CN.
    daily = method.annual(record_with([50.0] * 20)).runoff_mm[0]
    annual_shortcut = method.annual(record_with([1000.0])).runoff_mm[0]
    assert annual_shortcut / daily > 3.0
    assert cn.cn > 0


def test_rational_and_strange_bracket_scs() -> None:
    from app.engines.runoff.curve_number import CurveNumber

    rec = record_with([10.0] * 30 + [40.0] * 15 + [90.0] * 3)  # a monsoon: 1170 mm
    scs = SCSCNMethod(CurveNumber(78.0, "C", "II")).annual(rec).runoff_mm[0]
    rational = RationalMethod(0.35).annual(rec).runoff_mm[0]
    strange = StrangeMethod("average").annual(rec).runoff_mm[0]
    assert rational == pytest.approx(0.35 * 1170.0)
    assert 0 < strange < rational
    assert 0 < scs < rational
    good = StrangeMethod("good").annual(rec).runoff_mm[0]
    bad = StrangeMethod("bad").annual(rec).runoff_mm[0]
    assert bad < strange < good


def test_runoff_is_monotonic_in_rainfall() -> None:
    from app.engines.runoff.curve_number import CurveNumber

    method = SCSCNMethod(CurveNumber(75.0, "C", "II"))
    previous = -1.0
    for p in (5.0, 15.0, 30.0, 60.0, 120.0):
        q = method.annual(record_with([p])).runoff_mm[0]
        assert q >= previous
        previous = q
