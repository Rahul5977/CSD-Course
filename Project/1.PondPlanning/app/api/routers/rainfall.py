"""Rainfall statistics and the daily series (FR5). Real since P3."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import RainfallDep, SettingsDep
from app.engines.rainfall.service import (
    fetch_record,
    record_window,
    series_response,
    statistics_response,
)
from app.schemas.rainfall import RainfallSeries, RainfallStatistics

router = APIRouter(prefix="/rainfall", tags=["rainfall"])

Lon = Annotated[float, Query(ge=-180, le=180, description="Longitude, EPSG:4326")]
Lat = Annotated[float, Query(ge=-90, le=90, description="Latitude, EPSG:4326")]


@router.get("/statistics", response_model=RainfallStatistics)
def get_statistics(
    lon: Lon,
    lat: Lat,
    chain: RainfallDep,
    settings: SettingsDep,
    years: Annotated[int | None, Query(ge=5, le=50, description="Length of record")] = None,
) -> RainfallStatistics:
    """FR5: statistics computed from the record — not a raw dump.

    The design figure is ``dependable_75``, the annual rainfall equalled or
    exceeded in 75 % of years. Sizing to the mean produces a pond that fails in
    roughly half of them.
    """
    record = fetch_record(chain, lon, lat, years or settings.rainfall_years)
    return statistics_response(chain, record)


@router.get("/series", response_model=RainfallSeries)
def get_series(
    lon: Lon,
    lat: Lat,
    chain: RainfallDep,
    settings: SettingsDep,
    start: Annotated[date | None, Query(description="ISO date, inclusive")] = None,
    end: Annotated[date | None, Query(description="ISO date, inclusive")] = None,
) -> RainfallSeries:
    """The daily record.

    Exposed because SCS-CN must be applied per day and then summed; applied to an
    annual total it overestimates runoff two- to three-fold.
    """
    default_start, default_end = record_window(settings.rainfall_years)
    record = chain.daily(lon, lat, start or default_start, end or default_end)
    return series_response(record, chain)
