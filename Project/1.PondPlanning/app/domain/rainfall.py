"""Rainfall as a domain concept: a daily series with provenance, and the provider port."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from app.domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class DailyRainfall:
    """A gap-free daily record in millimetres, with where it came from.

    Raises:
        ValidationError: If the arrays disagree in length or the record is empty.
    """

    days: NDArray[np.datetime64]
    mm: NDArray[np.float64]
    source: str
    grid_label: str
    latitude: float
    longitude: float
    attribution: str
    fetched_live: bool = True

    def __post_init__(self) -> None:
        """Reject inconsistent or empty records."""
        if self.days.shape != self.mm.shape or self.days.size == 0:
            msg = "daily rainfall record is empty or inconsistent"
            raise ValidationError(msg, {"days": int(self.days.size), "values": int(self.mm.size)})

    @property
    def start(self) -> date:
        """First day."""
        return self.days[0].astype("datetime64[D]").astype(date)  # type: ignore[no-any-return]

    @property
    def end(self) -> date:
        """Last day."""
        return self.days[-1].astype("datetime64[D]").astype(date)  # type: ignore[no-any-return]

    @property
    def completeness(self) -> float:
        """Fraction of days with a value (NaN = missing)."""
        return float(np.mean(~np.isnan(self.mm)))


class RainfallProvider(Protocol):
    """Anything that can return a daily rainfall record for a point."""

    @property
    def name(self) -> str:
        """Short provider name, recorded as provenance."""
        ...

    def daily(self, lon: float, lat: float, start: date, end: date) -> DailyRainfall:
        """Fetch the inclusive daily record. Raises ``UpstreamUnavailableError`` on failure."""
        ...
