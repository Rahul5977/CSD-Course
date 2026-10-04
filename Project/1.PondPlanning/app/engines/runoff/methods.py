"""Three runoff-volume methods behind one Strategy interface (FR6, ADR 0010).

They disagree, and the disagreement is information: the result is a *range*.

1. **SCS-CN** (USDA-SCS 1972, TR-55 1986), applied to **each day** and summed:
   ``Q = (P - Ia)² / (P - Ia + S)`` for ``P > Ia``, ``S = 25400/CN - 254`` mm,
   ``Ia = 0.2 S``. Applying it to an annual total overestimates runoff 2-3x,
   because a year's rain does not fall in one storm.
2. **Runoff-coefficient ("rational") method**: ``Q = C · P``, with C an
   area-weighted ASCE coefficient by land cover. The rational method is a
   peak-flow formula; used for annual volume it is the crude upper bracket.
3. **Strange's tables** (Strange 1928, Madras Presidency; still in Indian
   minor-irrigation manuals): runoff per cent as a function of *daily*
   rainfall and catchment condition (good / average / bad). Applied per day.

Every method returns the annual runoff **depth series** (mm per year), so
the same Weibull 75 % dependable logic used for rainfall gives the design
runoff year — not the mean, which a pond misses every second year.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np
from numpy.typing import NDArray

from app.domain.rainfall import DailyRainfall
from app.engines.runoff.curve_number import CurveNumber

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class AnnualRunoff:
    """Per-year runoff depth and the rainfall it came from."""

    years: list[int]
    rainfall_mm: FloatArray
    runoff_mm: FloatArray

    @property
    def mean_coefficient(self) -> float:
        """Mean annual runoff / mean annual rainfall."""
        return float(self.runoff_mm.sum() / max(self.rainfall_mm.sum(), 1e-9))


class RunoffMethod(Protocol):
    """Strategy: daily rainfall → annual runoff depths."""

    @property
    def key(self) -> str:
        """Wire identifier (``scs_cn``, ``rational``, ``empirical_strange``)."""
        ...

    @property
    def reference(self) -> str:
        """Citation."""
        ...

    def annual(self, record: DailyRainfall) -> AnnualRunoff:
        """Runoff depth per complete calendar year."""
        ...

    def parameters(self) -> dict[str, tuple[float, str, str]]:
        """``name → (value, unit, note)`` for the response."""
        ...


def _by_year(record: DailyRainfall, daily_runoff: FloatArray, min_days: int = 350) -> AnnualRunoff:
    years = record.days.astype("datetime64[Y]").astype(int) + 1970
    valid = ~np.isnan(record.mm)
    out_years: list[int] = []
    rain: list[float] = []
    run: list[float] = []
    for year in np.unique(years):
        sel = (years == year) & valid
        if sel.sum() < min_days:
            continue
        out_years.append(int(year))
        rain.append(float(record.mm[sel].sum()))
        run.append(float(daily_runoff[sel].sum()))
    return AnnualRunoff(out_years, np.array(rain), np.array(run))


class SCSCNMethod:
    """Daily SCS-CN, summed by year."""

    key = "scs_cn"
    reference = "USDA-SCS (1972) National Engineering Handbook §4; TR-55 (1986)"

    def __init__(self, curve_number: CurveNumber, ia_ratio: float = 0.2) -> None:
        """``ia_ratio`` is the initial-abstraction ratio; 0.2 is the tabulated standard."""
        self.cn = curve_number
        self.ia_ratio = ia_ratio

    def annual(self, record: DailyRainfall) -> AnnualRunoff:
        """Apply the CN equation to every day, then sum by year."""
        s = self.cn.potential_retention_mm
        ia = self.ia_ratio * s
        p = np.nan_to_num(record.mm, nan=0.0)
        excess = np.maximum(p - ia, 0.0)
        q = np.where(p > ia, excess**2 / (excess + s), 0.0)
        return _by_year(record, q)

    def parameters(self) -> dict[str, tuple[float, str, str]]:
        """CN, S and Ia."""
        return {
            "curve_number": (
                self.cn.cn,
                "count",
                f"AMC {self.cn.amc}, HSG {self.cn.hsg}, area-weighted",
            ),
            "potential_retention_S": (self.cn.potential_retention_mm, "mm", "25400/CN - 254"),
            "initial_abstraction_ratio": (self.ia_ratio, "ratio", "Ia = 0.2 S, standard TR-55"),
        }


class RationalMethod:
    """Annual runoff = C x annual rainfall."""

    key = "rational"
    reference = "ASCE (1969) runoff coefficients; Kuichling (1889) rational formula"

    def __init__(self, coefficient: float) -> None:
        """``coefficient`` is the area-weighted C."""
        self.coefficient = coefficient

    def annual(self, record: DailyRainfall) -> AnnualRunoff:
        """Scale every day by C (equivalent to scaling the annual total)."""
        return _by_year(record, np.nan_to_num(record.mm, nan=0.0) * self.coefficient)

    def parameters(self) -> dict[str, tuple[float, str, str]]:
        """C."""
        return {"runoff_coefficient_C": (self.coefficient, "ratio", "area-weighted by land cover")}


#: Strange (1928): daily rainfall (mm) → runoff % for good / average / bad catchments.
#: Reproduced from Indian minor-irrigation manuals (e.g. Subramanya, Engineering Hydrology).
STRANGE_TABLE: tuple[tuple[float, float, float, float], ...] = (
    (25.4, 4, 3, 2),
    (50.8, 12, 9, 6),
    (76.2, 20, 15, 10),
    (101.6, 29, 22, 14),
    (127.0, 37, 28, 18),
    (152.4, 45, 34, 22),
    (177.8, 52, 39, 26),
    (203.2, 58, 44, 29),
    (228.6, 63, 47, 32),
    (254.0, 66, 50, 33),
)
CatchmentCondition = Literal["good", "average", "bad"]


class StrangeMethod:
    """Strange's runoff table applied per day."""

    key = "empirical_strange"
    reference = "Strange (1928), Madras PWD; as tabulated in Subramanya, Engineering Hydrology"

    def __init__(self, condition: CatchmentCondition = "average") -> None:
        """``condition`` describes the catchment's runoff-producing character."""
        self.condition = condition

    def annual(self, record: DailyRainfall) -> AnnualRunoff:
        """Interpolate runoff per cent by daily rainfall, then sum by year."""
        col = {"good": 1, "average": 2, "bad": 3}[self.condition]
        xs = np.array([0.0, *[row[0] for row in STRANGE_TABLE]])
        ys = np.array([0.0, *[row[col] for row in STRANGE_TABLE]])
        p = np.nan_to_num(record.mm, nan=0.0)
        pct = np.interp(p, xs, ys, right=float(ys[-1]))
        return _by_year(record, p * pct / 100.0)

    def parameters(self) -> dict[str, tuple[float, str, str]]:
        """Catchment condition as an index."""
        return {
            "catchment_condition": (
                {"good": 1.0, "average": 2.0, "bad": 3.0}[self.condition],
                "count",
                f"{self.condition} catchment (1 good, 2 average, 3 bad)",
            )
        }
