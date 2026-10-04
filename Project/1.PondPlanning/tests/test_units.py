"""Tests for the Quantity value object — the type that enforces the units rule."""

from __future__ import annotations

import pytest

from app.domain.units import Quantity, Unit


def test_uncertainty_band_brackets_the_value() -> None:
    q = Quantity(18950.0, Unit.CUBIC_METRE, uncertainty_pct=20)

    assert q.low == pytest.approx(15160.0)
    assert q.high == pytest.approx(22740.0)


def test_exact_quantities_have_a_degenerate_band() -> None:
    """None means 'exact by construction', not 'uncertainty unknown'."""
    q = Quantity(42, Unit.COUNT)

    assert q.low == q.high == 42


def test_negative_uncertainty_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        Quantity(1.0, Unit.METRE, uncertainty_pct=-5)


def test_conversion_preserves_uncertainty_and_method() -> None:
    area = Quantity(2_146_000.0, Unit.SQUARE_METRE, 15, "Upslope BFS over the D8 grid")

    hectares = area.to(Unit.HECTARE)

    assert hectares.value == pytest.approx(214.6)
    assert hectares.unit is Unit.HECTARE
    assert hectares.uncertainty_pct == 15
    assert hectares.method == "Upslope BFS over the D8 grid"


def test_converting_to_the_same_unit_is_a_no_op() -> None:
    q = Quantity(5.0, Unit.METRE)

    assert q.to(Unit.METRE) is q


def test_undefined_conversion_fails_loudly() -> None:
    """A sparse table that raises beats a general library nobody can predict."""
    with pytest.raises(ValueError, match="no conversion defined"):
        Quantity(5.0, Unit.METRE).to(Unit.CUBIC_METRE)


def test_str_carries_the_unit_and_the_band() -> None:
    """'18,950.00 m3 (±20 %)' beats '18950' — the rule this type exists to enforce."""
    rendered = str(Quantity(18950.0, Unit.CUBIC_METRE, 20))

    assert rendered == "18,950.00 m3 (±20 %)"


def test_quantity_is_immutable() -> None:
    q = Quantity(1.0, Unit.METRE)

    with pytest.raises(AttributeError):
        q.value = 2.0  # type: ignore[misc]
