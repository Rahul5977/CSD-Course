"""Land constraints as composable Specifications (FR3).

Specification pattern: each rule is an object with ``is_satisfied_by(ctx)``
returning a boolean raster, and rules combine with ``&``, ``|`` and ``~``,
so the eligibility of every cell reads as one expression::

    SlopeUnder(15) & ~WithinBuffer("water", 150) & ~WithinBuffer("built", 100)
    & MinFlowAccumulation(...) & MinContiguousArea(2500)

Every rule names itself, so the response can list exactly which constraints
were applied and which one rejected a parcel — "excluded_by" in the contract.
Ownership is the one rule that needs data the map cannot supply: with no
cadastral layer it is *unknown*, reported as such, never assumed government.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

BoolArray = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class LandContext:
    """The rasters the rules are evaluated on, all on the DEM grid."""

    cell_size_m: float
    slope_pct: NDArray[np.float64]
    accumulation: NDArray[np.int64]
    water: BoolArray  # existing water (NDWI mask or WorldCover class 80)
    built: BoolArray  # habitation (WorldCover class 50)
    landcover: NDArray[np.uint8]  # WorldCover codes
    ownership: NDArray[np.uint8] | None = None  # 1 government, 2 community, 3 private, 0 unknown
    extras: dict[str, NDArray[np.float64]] = field(default_factory=dict)


class Specification:
    """Base rule; subclasses implement :meth:`is_satisfied_by`."""

    name: str = "specification"

    def is_satisfied_by(self, ctx: LandContext) -> BoolArray:
        """Boolean raster of cells that satisfy the rule."""
        raise NotImplementedError

    def __and__(self, other: Specification) -> Specification:
        """Both rules."""
        return And(self, other)

    def __or__(self, other: Specification) -> Specification:
        """Either rule."""
        return Or(self, other)

    def __invert__(self) -> Specification:
        """The complement."""
        return Not(self)

    def names(self) -> list[str]:
        """Leaf rule names, for the response."""
        return [self.name]


class And(Specification):
    """Conjunction."""

    def __init__(self, left: Specification, right: Specification) -> None:
        """Combine two rules."""
        self.left, self.right = left, right
        self.name = f"({left.name} AND {right.name})"

    def is_satisfied_by(self, ctx: LandContext) -> BoolArray:
        """Elementwise and."""
        return self.left.is_satisfied_by(ctx) & self.right.is_satisfied_by(ctx)

    def names(self) -> list[str]:
        """Leaves of both sides."""
        return self.left.names() + self.right.names()


class Or(Specification):
    """Disjunction."""

    def __init__(self, left: Specification, right: Specification) -> None:
        """Combine two rules."""
        self.left, self.right = left, right
        self.name = f"({left.name} OR {right.name})"

    def is_satisfied_by(self, ctx: LandContext) -> BoolArray:
        """Elementwise or."""
        return self.left.is_satisfied_by(ctx) | self.right.is_satisfied_by(ctx)

    def names(self) -> list[str]:
        """Leaves of both sides."""
        return self.left.names() + self.right.names()


class Not(Specification):
    """Complement."""

    def __init__(self, inner: Specification) -> None:
        """Negate a rule."""
        self.inner = inner
        self.name = f"NOT {inner.name}"

    def is_satisfied_by(self, ctx: LandContext) -> BoolArray:
        """Elementwise not."""
        return ~self.inner.is_satisfied_by(ctx)

    def names(self) -> list[str]:
        """The negated leaf."""
        return [self.name]


class SlopeUnder(Specification):
    """Slope below a per-cent threshold (earthwork and seepage both worsen with slope)."""

    def __init__(self, max_pct: float) -> None:
        """``max_pct`` in per cent."""
        self.max_pct = max_pct
        self.name = f"slope < {max_pct:g} %"

    def is_satisfied_by(self, ctx: LandContext) -> BoolArray:
        """Cells at or below the threshold."""
        return np.asarray(ctx.slope_pct <= self.max_pct, dtype=bool)


class WithinBuffer(Specification):
    """Cells within ``distance_m`` of a mask ('water' or 'built'). Usually negated."""

    def __init__(self, layer: str, distance_m: float) -> None:
        """``layer`` selects ``ctx.water`` or ``ctx.built``."""
        self.layer, self.distance_m = layer, distance_m
        self.name = f"within {distance_m:g} m of {layer}"

    def is_satisfied_by(self, ctx: LandContext) -> BoolArray:
        """Euclidean distance transform on the grid."""
        mask = ctx.water if self.layer == "water" else ctx.built
        if not mask.any():
            return np.zeros(mask.shape, dtype=bool)
        distance = ndimage.distance_transform_edt(~mask) * ctx.cell_size_m
        return np.asarray(distance <= self.distance_m, dtype=bool)


class MinFlowAccumulation(Specification):
    """At least this much upstream area drains to the cell (the pond must receive runoff)."""

    def __init__(self, min_area_m2: float) -> None:
        """``min_area_m2`` upstream."""
        self.min_area_m2 = min_area_m2
        self.name = f"upstream area >= {min_area_m2 / 1e4:g} ha"

    def is_satisfied_by(self, ctx: LandContext) -> BoolArray:
        """Cells whose accumulation meets the area."""
        cells = max(1, round(self.min_area_m2 / (ctx.cell_size_m**2)))
        return np.asarray(ctx.accumulation >= cells, dtype=bool)


class HabitationDistance(Specification):
    """Between ``min_m`` and ``max_m`` from habitation: usable, yet safely distant."""

    def __init__(self, min_m: float, max_m: float) -> None:
        """Distance band in metres."""
        self.min_m, self.max_m = min_m, max_m
        self.name = f"{min_m:g}-{max_m:g} m from habitation"

    def is_satisfied_by(self, ctx: LandContext) -> BoolArray:
        """Cells in the band; everything qualifies if there is no habitation on the map."""
        if not ctx.built.any():
            return np.ones(ctx.built.shape, dtype=bool)
        distance = ndimage.distance_transform_edt(~ctx.built) * ctx.cell_size_m
        return np.asarray((distance >= self.min_m) & (distance <= self.max_m), dtype=bool)


class LandCoverIn(Specification):
    """Cells whose WorldCover class is in the allowed set (not built-up, water or forest)."""

    def __init__(self, codes: tuple[int, ...], label: str) -> None:
        """``codes`` are WorldCover class codes."""
        self.codes, self.name = codes, f"land cover in {label}"

    def is_satisfied_by(self, ctx: LandContext) -> BoolArray:
        """Membership test."""
        return np.asarray(np.isin(ctx.landcover, self.codes), dtype=bool)


class IsGovernmentLand(Specification):
    """Ownership class is government/community. Unknown ownership passes with a warning upstream."""

    name = "government or community land (or ownership unknown)"

    def is_satisfied_by(self, ctx: LandContext) -> BoolArray:
        """Without cadastral data every cell is 'unknown' and passes; the response says so."""
        if ctx.ownership is None:
            return np.ones(ctx.slope_pct.shape, dtype=bool)
        return np.asarray(np.isin(ctx.ownership, (0, 1, 2)), dtype=bool)


class MinContiguousArea(Specification):
    """Keep only connected eligible patches of at least ``min_m2`` (a pond needs room)."""

    def __init__(self, inner: Specification, min_m2: float) -> None:
        """Applied *after* ``inner`` so the patches are of eligible cells."""
        self.inner, self.min_m2 = inner, min_m2
        self.name = f"contiguous >= {min_m2:g} m2"

    def is_satisfied_by(self, ctx: LandContext) -> BoolArray:
        """Connected-component filter (8-connectivity)."""
        mask = self.inner.is_satisfied_by(ctx)
        labels, count = ndimage.label(mask, structure=np.ones((3, 3)))
        if count == 0:
            return mask
        sizes = ndimage.sum(mask, labels, index=np.arange(1, count + 1))
        keep = np.zeros(count + 1, dtype=bool)
        keep[1:] = sizes * ctx.cell_size_m**2 >= self.min_m2
        return np.asarray(keep[labels], dtype=bool)

    def names(self) -> list[str]:
        """Inner leaves plus this filter."""
        return [*self.inner.names(), self.name]
