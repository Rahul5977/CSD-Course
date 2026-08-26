"""SCS curve numbers from land cover and hydrologic soil group.

**Curve Number (CN)** is the USDA-SCS (1972) / TR-55 (1986) index of a
catchment's runoff potential: 30 for deep sand under forest, 98 for
pavement. It is looked up from (land cover, hydrologic soil group) and then
**area-weighted** over the catchment — a Flyweight table, not a raster of
floats, because there are eleven WorldCover classes and four soil groups.

**Hydrologic soil group** (A-D, most to least permeable) is inferred from
SoilGrids texture with the USDA rule of thumb: sand-dominated → A, loam →
B, clay-loam → C, clay → D. India's Vertisols (black cotton soils) are D;
the alluvial and red loams of Chhattisgarh mostly C.

**Antecedent moisture** (AMC I dry / II average / III wet) shifts CN by the
Hawkins (1985) formulas; AMC II is the tabulated condition and the default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from app.domain.soil import HSG, hsg_from_texture

#: ESA WorldCover v200 class codes.
WORLDCOVER_NAMES: dict[int, str] = {
    10: "tree cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built-up",
    60: "bare / sparse vegetation",
    70: "snow and ice",
    80: "permanent water",
    90: "herbaceous wetland",
    95: "mangroves",
    100: "moss and lichen",
}

#: TR-55 Table 2-2 (a-d), AMC II, mapped onto WorldCover classes. Cropland is
#: "row crops, straight row, poor condition"; grassland is "pasture, fair";
#: built-up is "residential, 1/4 acre lots" (38 % impervious).
CN_TABLE: dict[int, dict[HSG, int]] = {
    10: {"A": 36, "B": 60, "C": 73, "D": 79},  # woods, fair
    20: {"A": 35, "B": 56, "C": 70, "D": 77},  # brush, fair
    30: {"A": 49, "B": 69, "C": 79, "D": 84},  # pasture, fair
    40: {"A": 72, "B": 81, "C": 88, "D": 91},  # row crops, straight row, poor
    50: {"A": 61, "B": 75, "C": 83, "D": 87},  # residential 1/4 acre
    60: {"A": 77, "B": 86, "C": 91, "D": 94},  # fallow, bare soil
    70: {"A": 98, "B": 98, "C": 98, "D": 98},
    80: {"A": 100, "B": 100, "C": 100, "D": 100},  # open water: all rain becomes "runoff"
    90: {"A": 30, "B": 58, "C": 71, "D": 78},  # wetland ~ meadow
    95: {"A": 30, "B": 58, "C": 71, "D": 78},
    100: {"A": 68, "B": 79, "C": 86, "D": 89},
}

#: Rational-method runoff coefficient C by WorldCover class (flat-to-rolling land, ASCE ranges).
RUNOFF_COEFFICIENT: dict[int, float] = {
    10: 0.15,
    20: 0.20,
    30: 0.25,
    40: 0.35,
    50: 0.60,
    60: 0.45,
    70: 0.80,
    80: 1.00,
    90: 0.20,
    95: 0.20,
    100: 0.40,
}


def amc_adjust(cn2: float, condition: Literal["I", "II", "III"]) -> float:
    """Hawkins et al. (1985) conversion of an AMC II curve number."""
    if condition == "I":
        return 4.2 * cn2 / (10 - 0.058 * cn2)
    if condition == "III":
        return 23 * cn2 / (10 + 0.13 * cn2)
    return cn2


@dataclass(frozen=True, slots=True)
class CurveNumber:
    """The composite CN and how it was assembled."""

    cn: float
    hsg: HSG
    amc: Literal["I", "II", "III"]
    class_fractions: dict[int, float] = field(default_factory=dict)  # WorldCover code → share
    class_cn: dict[int, int] = field(default_factory=dict)
    runoff_coefficient: float = 0.3
    source: str = ""

    @property
    def potential_retention_mm(self) -> float:
        """S = 25400 / CN - 254 (millimetres)."""
        return 25400.0 / self.cn - 254.0


def composite_curve_number(
    landcover: NDArray[np.integer],
    hsg: HSG,
    amc: Literal["I", "II", "III"] = "II",
    source: str = "",
) -> CurveNumber:
    """Area-weighted CN (and rational C) over a land-cover array of WorldCover codes."""
    codes, counts = np.unique(landcover[landcover > 0], return_counts=True)
    total = counts.sum()
    if total == 0:
        msg_cn = CN_TABLE[40][hsg]
        return CurveNumber(
            float(amc_adjust(msg_cn, amc)), hsg, amc, {}, {}, RUNOFF_COEFFICIENT[40], source
        )
    fractions = {int(c): float(n / total) for c, n in zip(codes, counts, strict=True)}
    cn2 = sum(f * CN_TABLE.get(code, CN_TABLE[40])[hsg] for code, f in fractions.items())
    coefficient = sum(f * RUNOFF_COEFFICIENT.get(code, 0.35) for code, f in fractions.items())
    return CurveNumber(
        cn=float(amc_adjust(cn2, amc)),
        hsg=hsg,
        amc=amc,
        class_fractions=fractions,
        class_cn={code: CN_TABLE.get(code, CN_TABLE[40])[hsg] for code in fractions},
        runoff_coefficient=float(coefficient),
        source=source,
    )


__all__ = [
    "CN_TABLE",
    "HSG",
    "CurveNumber",
    "amc_adjust",
    "composite_curve_number",
    "hsg_from_texture",
]
