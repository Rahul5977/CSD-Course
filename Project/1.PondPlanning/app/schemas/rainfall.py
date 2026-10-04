"""Rainfall contracts (FR5)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import QuantityOut, ResultWarning


class RainfallDaily(BaseModel):
    """One day of the record.

    The daily series is exposed, not only the annual totals, because SCS-CN must
    be applied per day and then summed. Applied to an annual total it
    overestimates runoff by two to three times — a common and very visible error.
    """

    day: date
    rainfall: QuantityOut


class RainfallSeries(BaseModel):
    """The daily record backing every rainfall statistic."""

    source: str
    station_or_grid: str
    latitude: float
    longitude: float
    start: date
    end: date
    days: int
    series: list[RainfallDaily]
    warnings: list[ResultWarning] = Field(default_factory=list)


class MonthlyNormal(BaseModel):
    """Long-term mean for one calendar month."""

    month: int = Field(ge=1, le=12)
    mean_rainfall: QuantityOut
    rainy_days: QuantityOut


class RainfallStatistics(BaseModel):
    """FR5: statistics computed from the record, not a raw dump.

    ``dependable_75`` is the design figure: the annual rainfall equalled or
    exceeded in 75 % of years. Designing to the mean produces a pond that fails
    roughly half the time, which is why practice uses the 75 % dependable value.
    """

    source: str
    years_of_record: int
    start_year: int
    end_year: int
    mean_annual: QuantityOut
    median_annual: QuantityOut
    dependable_75: QuantityOut
    coefficient_of_variation: QuantityOut
    monsoon_share: QuantityOut = Field(description="Fraction of annual rainfall in Jun-Sep")
    max_daily_recorded: QuantityOut
    rainy_days_mean: QuantityOut
    monthly_normals: list[MonthlyNormal]
    data_completeness: QuantityOut
    fallback_used: Literal["none", "cache", "secondary_provider"] = Field(
        default="none",
        description="How the data was obtained. 'cache' means the live API was unreachable.",
    )
    attribution: str
    warnings: list[ResultWarning] = Field(default_factory=list)
