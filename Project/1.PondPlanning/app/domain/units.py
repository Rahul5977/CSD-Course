"""Units and uncertainty as first-class domain concepts.

The standing rule for this project is that **every numeric output carries its
unit and an uncertainty statement** — "Gross storage: 18,950 m³ (±20 %)" rather
than "18950". Enforcing that in prose fails: someone eventually returns a bare
float. Enforcing it in the type makes the correct thing the easy thing, because
there is no way to construct a result without saying what it means.

The uncertainty is a plain symmetric percentage rather than a full error
distribution. That is a deliberate limit: the dominant error term in this system
is the DEM's vertical accuracy (SRTM is roughly ±6 m relative, ±16 m absolute at
LE90), which propagates non-linearly through the elevation-area-volume curve.
Reporting a single honest band with its provenance is defensible; reporting a
confidence interval we cannot actually derive would not be.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Unit(StrEnum):
    """Units used anywhere in the system. SI, except where the domain differs.

    Indian minor-irrigation practice reports catchment in hectares and storage in
    cubic metres, so those are the reporting units even though the engine
    computes in square metres.
    """

    METRE = "m"
    SQUARE_METRE = "m2"
    HECTARE = "ha"
    SQUARE_KILOMETRE = "km2"
    CUBIC_METRE = "m3"
    MILLIMETRE = "mm"
    MILLIMETRE_PER_YEAR = "mm/yr"
    DEGREE = "deg"
    PERCENT = "%"
    RATIO = "ratio"
    COUNT = "count"
    YEAR = "yr"
    DAY = "d"
    INR = "INR"


@dataclass(frozen=True, slots=True)
class Quantity:
    """A number that knows what it means.

    Attributes:
        value: The magnitude.
        unit: The unit of ``value``.
        uncertainty_pct: Symmetric relative uncertainty, in percent. ``None``
            means the quantity is exact by construction — a count, or a value the
            user supplied — not that its uncertainty is unknown.
        method: How the value was obtained, e.g. ``"SCS-CN on daily series"``.
            Carried into the API response so an evaluator can see the provenance
            of every number without reading the code.

    Raises:
        ValueError: If ``uncertainty_pct`` is negative.
    """

    value: float
    unit: Unit
    uncertainty_pct: float | None = None
    method: str | None = None

    def __post_init__(self) -> None:
        """Reject an uncertainty that cannot be interpreted."""
        if self.uncertainty_pct is not None and self.uncertainty_pct < 0:
            msg = f"uncertainty_pct must be non-negative, got {self.uncertainty_pct}"
            raise ValueError(msg)

    @property
    def low(self) -> float:
        """Lower bound of the uncertainty band (the value itself when exact)."""
        if self.uncertainty_pct is None:
            return self.value
        return self.value * (1 - self.uncertainty_pct / 100)

    @property
    def high(self) -> float:
        """Upper bound of the uncertainty band (the value itself when exact)."""
        if self.uncertainty_pct is None:
            return self.value
        return self.value * (1 + self.uncertainty_pct / 100)

    def to(self, unit: Unit) -> Quantity:
        """Convert to a compatible unit, preserving uncertainty and method.

        Raises:
            ValueError: If no conversion between the two units is defined.
        """
        if unit == self.unit:
            return self
        factor = _CONVERSIONS.get((self.unit, unit))
        if factor is None:
            msg = f"no conversion defined from {self.unit} to {unit}"
            raise ValueError(msg)
        return Quantity(self.value * factor, unit, self.uncertainty_pct, self.method)

    def __str__(self) -> str:
        """Render as it should appear to a human, band included."""
        base = f"{self.value:,.2f} {self.unit.value}"
        return base if self.uncertainty_pct is None else f"{base} (±{self.uncertainty_pct:g} %)"


# Only conversions the system actually performs. A sparse table that fails loudly
# beats a general unit library whose behaviour nobody on the project can predict.
_CONVERSIONS: dict[tuple[Unit, Unit], float] = {
    (Unit.SQUARE_METRE, Unit.HECTARE): 1e-4,
    (Unit.HECTARE, Unit.SQUARE_METRE): 1e4,
    (Unit.SQUARE_METRE, Unit.SQUARE_KILOMETRE): 1e-6,
    (Unit.SQUARE_KILOMETRE, Unit.SQUARE_METRE): 1e6,
    (Unit.HECTARE, Unit.SQUARE_KILOMETRE): 1e-2,
    (Unit.SQUARE_KILOMETRE, Unit.HECTARE): 1e2,
    (Unit.MILLIMETRE, Unit.METRE): 1e-3,
    (Unit.METRE, Unit.MILLIMETRE): 1e3,
    (Unit.RATIO, Unit.PERCENT): 1e2,
    (Unit.PERCENT, Unit.RATIO): 1e-2,
}
