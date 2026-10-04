"""Golden tests: AHP consistency, Specification constraints, NDWI/OpenCV water mask."""

from __future__ import annotations

import numpy as np
import pytest

from app.domain.errors import ValidationError
from app.engines.suitability.ahp import DEFAULT_MATRIX, ahp_weights
from app.engines.suitability.constraints import (
    HabitationDistance,
    IsGovernmentLand,
    LandContext,
    MinContiguousArea,
    MinFlowAccumulation,
    SlopeUnder,
    WithinBuffer,
)
from app.engines.suitability.water_mask import combine_seasons, ndwi, water_mask_from_ndwi

pytestmark = pytest.mark.golden


def test_ahp_default_matrix_is_consistent_and_weights_sum_to_one() -> None:
    result = ahp_weights(DEFAULT_MATRIX)
    assert result.acceptable and result.consistency_ratio < 0.10
    assert sum(result.weights.values()) == pytest.approx(1.0)
    assert result.weights["upstream_area"] == pytest.approx(result.weights["impoundment"], rel=1e-6)
    assert result.weights["upstream_area"] > result.weights["flatness"] > result.weights["wetness"]


def test_ahp_perfectly_consistent_matrix_has_zero_cr() -> None:
    w = np.array([0.5, 0.3, 0.2])
    matrix = np.outer(w, 1 / w)  # a_ij = w_i / w_j is perfectly consistent
    result = ahp_weights(matrix, ("a", "b", "c"))
    assert result.consistency_ratio == pytest.approx(0.0, abs=1e-9)
    assert [result.weights[k] for k in "abc"] == pytest.approx(list(w))


def test_ahp_rejects_inconsistent_judgements() -> None:
    # A >> B, B >> C, but C >> A: strongly intransitive.
    matrix = ((1, 9, 1 / 9), (1 / 9, 1, 9), (9, 1 / 9, 1))
    result = ahp_weights(matrix, ("a", "b", "c"))
    assert not result.acceptable and result.consistency_ratio > 0.10
    with pytest.raises(ValidationError):
        ahp_weights(((1, 2), (3, 1)), ("a", "b"))  # not reciprocal


def context() -> LandContext:
    rows, cols = 20, 30
    slope = np.full((rows, cols), 2.0)
    slope[:, 25:] = 20.0  # a steep strip on the east
    acc = np.ones((rows, cols), dtype=np.int64)
    acc[10, :] = 500  # a channel along row 10
    water = np.zeros((rows, cols), dtype=bool)
    water[0:3, 0:3] = True  # a tank in the north-west corner
    built = np.zeros((rows, cols), dtype=bool)
    built[17:20, 12:16] = True  # a hamlet in the south
    lc = np.full((rows, cols), 40, dtype=np.uint8)
    return LandContext(10.0, slope, acc, water, built, lc)


def test_specifications_compose_and_name_themselves() -> None:
    ctx = context()
    rule = SlopeUnder(15) & ~WithinBuffer("water", 50) & MinFlowAccumulation(10 * 100.0)
    mask = rule.is_satisfied_by(ctx)
    assert mask[10, 10] and not mask[10, 27], "steep strip excluded"
    assert not mask[4, 2], "within 50 m of the tank"
    assert not mask[5, 10], "no channel there"
    assert rule.names() == ["slope < 15 %", "NOT within 50 m of water", "upstream area >= 0.1 ha"]
    band = HabitationDistance(30, 100).is_satisfied_by(ctx)
    assert band[12, 13] and not band[16, 13] and not band[2, 13]
    assert IsGovernmentLand().is_satisfied_by(ctx).all(), (
        "unknown ownership passes, flagged upstream"
    )


def test_min_contiguous_area_drops_slivers() -> None:
    ctx = context()
    rule = MinContiguousArea(SlopeUnder(15) & MinFlowAccumulation(10 * 100.0), min_m2=1500.0)
    mask = rule.is_satisfied_by(ctx)
    assert mask[10, :25].all(), "the 25-cell channel patch (2 500 m2) survives"
    tiny = MinContiguousArea(SlopeUnder(15) & MinFlowAccumulation(10 * 100.0), min_m2=10_000.0)
    assert not tiny.is_satisfied_by(ctx).any()


def test_ndwi_water_mask_finds_a_lake_and_drops_noise() -> None:
    rng = np.random.default_rng(3)
    green = rng.normal(1200, 60, (80, 100))
    nir = rng.normal(2600, 80, (80, 100))  # land: NIR >> green
    green[30:50, 40:70] = 900
    nir[30:50, 40:70] = 300  # lake: green > NIR
    green[5, 5], nir[5, 5] = 900, 300  # one noisy pixel
    index = ndwi(green, nir)
    result = water_mask_from_ndwi(index, pixel_size_m=10.0, min_area_m2=500.0)
    assert result.mask[40, 55] and not result.mask[10, 10]
    assert not result.mask[5, 5], "single pixel removed by opening / area filter"
    assert result.components_after == 1 and result.components_before >= 1
    assert 0.0 <= result.otsu_threshold < 0.8  # Otsu, or the NDWI > 0 rule
    assert result.water_fraction == pytest.approx(600 / 8000, rel=0.15)
    perennial, seasonal = combine_seasons(
        result.mask, result.mask | np.roll(result.mask, 30, axis=1)
    )
    assert perennial.sum() == result.mask.sum() and seasonal.sum() > 0
