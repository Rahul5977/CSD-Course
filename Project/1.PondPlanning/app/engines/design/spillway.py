"""Spillway sizing for the 25-year storm.

Peak inflow by the **rational method** ``Q = C * i * A`` with the design
intensity from the 25-year 1-day rainfall reduced to the catchment's time
of concentration with the IMD short-duration relation
``P_t = P_24 * (t/24)^(1/3)`` (Indian Meteorological Department; used by
CWC). Time of concentration by **Kirpich (1940)**:
``t_c = 0.0195 * L^0.77 * S^-0.385`` minutes (L in m, S the mean slope).
The weir length follows from the broad-crested weir formula
``Q = 1.7 * L * H^1.5`` with a 0.3 m design head.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpillwayDesign:
    """Peak flow and the weir that passes it."""

    time_of_concentration_min: float
    design_intensity_mm_hr: float
    peak_flow_m3_s: float
    weir_length_m: float
    design_head_m: float


def size_spillway(
    *,
    rainfall_25y_1day_mm: float,
    longest_flow_path_m: float,
    mean_slope_ratio: float,
    catchment_area_m2: float,
    runoff_coefficient: float,
    design_head_m: float = 0.3,
) -> SpillwayDesign:
    """Rational-method peak at t_c, broad-crested weir length."""
    slope = max(mean_slope_ratio, 0.001)
    length = max(longest_flow_path_m, 30.0)
    tc_min = 0.0195 * length**0.77 * slope**-0.385
    tc_hr = max(tc_min / 60.0, 0.1)
    p_tc = rainfall_25y_1day_mm * (tc_hr / 24.0) ** (1.0 / 3.0)
    intensity = p_tc / tc_hr  # mm/hr
    q_peak = runoff_coefficient * (intensity / 1000.0 / 3600.0) * catchment_area_m2  # m³/s
    weir_length = q_peak / (1.7 * design_head_m**1.5)
    return SpillwayDesign(tc_min, intensity, q_peak, max(weir_length, 1.0), design_head_m)
