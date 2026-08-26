"""Excavated-pond geometry: an inverted truncated pyramid (frustum).

Volume by the **prismoidal formula** ``V = D/3 * (A_top + A_bot + sqrt(A_top*A_bot))``,
exact for a frustum with plane sides. Side slope ``z`` is horizontal:vertical
(2:1 is the usual earthen slope in Indian farm-pond manuals); the bottom is
the top inset by ``z*D`` on every side. Freeboard sits above the design
water level and is not counted as storage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PondGeometry:
    """An excavated pond, fully specified."""

    depth_m: float  # water depth below the top edge, excluding freeboard
    top_length_m: float
    top_width_m: float
    side_slope: float  # H:V
    freeboard_m: float

    @property
    def bottom_length_m(self) -> float:
        """Top length inset by the side slopes."""
        return self.top_length_m - 2 * self.side_slope * self.depth_m

    @property
    def bottom_width_m(self) -> float:
        """Top width inset by the side slopes."""
        return self.top_width_m - 2 * self.side_slope * self.depth_m

    @property
    def feasible(self) -> bool:
        """Bottom must exist and be workable by machinery."""
        return self.bottom_length_m >= 5.0 and self.bottom_width_m >= 5.0

    @property
    def top_area_m2(self) -> float:
        """Water-surface area when full."""
        return self.top_length_m * self.top_width_m

    @property
    def bottom_area_m2(self) -> float:
        """Floor area."""
        return max(self.bottom_length_m, 0.0) * max(self.bottom_width_m, 0.0)

    @property
    def storage_m3(self) -> float:
        """Prismoidal volume of the water body."""
        a1, a2 = self.top_area_m2, self.bottom_area_m2
        return self.depth_m / 3.0 * (a1 + a2 + math.sqrt(a1 * a2))

    @property
    def excavation_m3(self) -> float:
        """Cut volume: the storage plus the freeboard band (same slopes)."""
        total_depth = self.depth_m + self.freeboard_m
        top_l = self.top_length_m + 2 * self.side_slope * self.freeboard_m
        top_w = self.top_width_m + 2 * self.side_slope * self.freeboard_m
        a1 = top_l * top_w
        a2 = self.bottom_area_m2
        return total_depth / 3.0 * (a1 + a2 + math.sqrt(a1 * a2))

    @property
    def perimeter_m(self) -> float:
        """Top-edge perimeter, for the bund."""
        return 2 * (self.top_length_m + self.top_width_m)

    def embankment_m3(
        self, height_m: float = 1.0, top_width_m: float = 2.0, slope: float = 2.0
    ) -> float:
        """Spoil bund around the rim: trapezoid section x perimeter."""
        section = height_m * (top_width_m + slope * height_m)
        return section * self.perimeter_m

    def area_at_level(self, level_m: float) -> float:
        """Water-surface area at ``level_m`` above the floor (for the EAV table)."""
        h = min(max(level_m, 0.0), self.depth_m)
        length = self.bottom_length_m + 2 * self.side_slope * h
        width = self.bottom_width_m + 2 * self.side_slope * h
        return length * width

    def volume_at_level(self, level_m: float) -> float:
        """Stored volume at ``level_m`` above the floor."""
        h = min(max(level_m, 0.0), self.depth_m)
        a2 = self.bottom_area_m2
        a1 = self.area_at_level(h)
        return h / 3.0 * (a1 + a2 + math.sqrt(a1 * a2))


def solve_top_dimensions(
    target_m3: float, depth_m: float, aspect: float, side_slope: float
) -> tuple[float, float] | None:
    """Top length/width (L = aspect*W) whose frustum holds ``target_m3`` at ``depth_m``.

    Bisection on W; ``None`` if no feasible bottom exists at that depth.
    """
    lo, hi = 2 * side_slope * depth_m + 5.0, 2000.0
    if PondGeometry(depth_m, aspect * lo, lo, side_slope, 0.0).storage_m3 > target_m3:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        geometry = PondGeometry(depth_m, aspect * mid, mid, side_slope, 0.0)
        if geometry.storage_m3 < target_m3:
            lo = mid
        else:
            hi = mid
    return aspect * hi, hi
