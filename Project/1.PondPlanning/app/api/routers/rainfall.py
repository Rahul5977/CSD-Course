"""Rainfall statistics and the daily series (FR5)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import FixtureRoute
from app.providers import fixtures
from app.schemas.rainfall import RainfallSeries, RainfallStatistics

router = APIRouter(prefix="/rainfall", tags=["rainfall"], dependencies=[FixtureRoute])

Lon = Annotated[float, Query(ge=-180, le=180, description="Longitude, EPSG:4326")]
Lat = Annotated[float, Query(ge=-90, le=90, description="Latitude, EPSG:4326")]


@router.get("/statistics", response_model=RainfallStatistics)
def get_statistics(
    lon: Lon,
    lat: Lat,
    years: Annotated[int, Query(ge=5, le=50, description="Length of record to analyse")] = 20,
) -> RainfallStatistics:
    """FR5: statistics computed from the record — not a raw dump.

    The design figure is ``dependable_75``, the annual rainfall equalled or
    exceeded in 75 % of years. Sizing to the mean produces a pond that fails in
    roughly half of them.
    """
    return RainfallStatistics.model_validate(fixtures.load("rainfall_statistics"))


@router.get("/series", response_model=RainfallSeries)
def get_series(
    lon: Lon,
    lat: Lat,
    start: Annotated[str | None, Query(description="ISO date, inclusive")] = None,
    end: Annotated[str | None, Query(description="ISO date, inclusive")] = None,
) -> RainfallSeries:
    """The daily record.

    Exposed because SCS-CN must be applied per day and then summed; applied to an
    annual total it overestimates runoff two- to three-fold.
    """
    return RainfallSeries.model_validate(fixtures.load("rainfall_series"))
