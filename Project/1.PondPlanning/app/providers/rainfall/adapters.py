"""Concrete rainfall providers.

Both live adapters use the standard library only: one GET with a timeout.
Neither needs a key. Both return the same :class:`DailyRainfall` so the
statistics engine cannot tell them apart — that is the point of the port.

- **Open-Meteo archive** (ERA5-Land reanalysis, ~9 km, daily from 1940;
  the 1981+ window is used because ERA5-Land quality is best there).
- **NASA POWER** (MERRA-2, ~50 km, daily from 1981), the secondary source.
- **Recorded** — a checked-in response, for tests, CI and an offline demo.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np

from app.domain.errors import UpstreamUnavailableError
from app.domain.rainfall import DailyRainfall

USER_AGENT = "pond-planner/0.1 (university assignment)"


def _get_json(url: str, timeout_s: float, provider: str) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return dict(json.loads(response.read().decode("utf-8")))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        msg = f"{provider} unreachable: {exc}"
        raise UpstreamUnavailableError(msg, {"provider": provider, "url": url}) from exc


class OpenMeteoAdapter:
    """Open-Meteo historical weather API — ERA5-Land daily precipitation."""

    name = "open_meteo_era5_land"
    BASE = "https://archive-api.open-meteo.com/v1/archive"

    def __init__(self, timeout_s: float = 30.0) -> None:
        """Configure the request timeout."""
        self._timeout = timeout_s

    def daily(self, lon: float, lat: float, start: date, end: date) -> DailyRainfall:
        """Fetch ``precipitation_sum`` for the inclusive range."""
        query = urllib.parse.urlencode(
            {
                "latitude": f"{lat:.4f}",
                "longitude": f"{lon:.4f}",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": "precipitation_sum",
                "timezone": "auto",
            }
        )
        doc = _get_json(f"{self.BASE}?{query}", self._timeout, self.name)
        return parse_open_meteo(doc, lon, lat)


def parse_open_meteo(doc: dict[str, object], lon: float, lat: float) -> DailyRainfall:
    """Turn an Open-Meteo archive response into a record."""
    daily = doc.get("daily")
    if not isinstance(daily, dict) or "time" not in daily or "precipitation_sum" not in daily:
        msg = "open_meteo: unexpected response shape"
        raise UpstreamUnavailableError(msg, {"keys": sorted(doc)})
    days = np.array(daily["time"], dtype="datetime64[D]")
    mm = np.array([np.nan if v is None else float(v) for v in daily["precipitation_sum"]])
    cell_lat = float(str(doc.get("latitude", lat)))
    cell_lon = float(str(doc.get("longitude", lon)))
    return DailyRainfall(
        days=days,
        mm=mm,
        source="Open-Meteo archive (ERA5-Land reanalysis, ~9 km)",
        grid_label=f"ERA5-Land cell {cell_lat:.3f}N {cell_lon:.3f}E",
        latitude=lat,
        longitude=lon,
        attribution="Open-Meteo.com (CC BY 4.0); ERA5-Land © ECMWF / Copernicus C3S",
    )


class NASAPowerAdapter:
    """NASA POWER daily point API — MERRA-2 corrected precipitation."""

    name = "nasa_power"
    BASE = "https://power.larc.nasa.gov/api/temporal/daily/point"

    def __init__(self, timeout_s: float = 45.0) -> None:
        """Configure the request timeout."""
        self._timeout = timeout_s

    def daily(self, lon: float, lat: float, start: date, end: date) -> DailyRainfall:
        """Fetch ``PRECTOTCORR`` for the inclusive range."""
        query = urllib.parse.urlencode(
            {
                "parameters": "PRECTOTCORR",
                "community": "AG",
                "longitude": f"{lon:.4f}",
                "latitude": f"{lat:.4f}",
                "start": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"),
                "format": "JSON",
            }
        )
        doc = _get_json(f"{self.BASE}?{query}", self._timeout, self.name)
        return parse_nasa_power(doc, lon, lat)


def parse_nasa_power(doc: dict[str, object], lon: float, lat: float) -> DailyRainfall:
    """Turn a NASA POWER response into a record. ``-999`` is POWER's missing value."""
    try:
        values = doc["properties"]["parameter"]["PRECTOTCORR"]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        msg = "nasa_power: unexpected response shape"
        raise UpstreamUnavailableError(msg, {"keys": sorted(doc)}) from exc
    keys = sorted(values)
    days = np.array([f"{k[:4]}-{k[4:6]}-{k[6:8]}" for k in keys], dtype="datetime64[D]")
    mm = np.array(
        [np.nan if values[k] is None or values[k] < 0 else float(values[k]) for k in keys]
    )
    return DailyRainfall(
        days=days,
        mm=mm,
        source="NASA POWER (MERRA-2, ~50 km)",
        grid_label=f"POWER cell {lat:.2f}N {lon:.2f}E",
        latitude=lat,
        longitude=lon,
        attribution="NASA POWER Project, Langley Research Center (public domain)",
    )


class RecordedAdapter:
    """A checked-in Open-Meteo response, sliced to the requested range.

    Used by the tests and by an offline demo. Refuses points more than ~0.5°
    from the recorded one, so it can never masquerade as data for elsewhere.
    """

    name = "recorded_open_meteo"

    def __init__(self, path: Path) -> None:
        """Load the JSON file lazily on first use."""
        self._path = path
        self._doc: dict[str, object] | None = None

    def daily(self, lon: float, lat: float, start: date, end: date) -> DailyRainfall:
        """Slice the recorded record to ``[start, end]``."""
        if self._doc is None:
            self._doc = dict(json.loads(self._path.read_text()))
        rec_lat, rec_lon = float(self._doc["latitude"]), float(self._doc["longitude"])  # type: ignore[arg-type]
        if abs(rec_lat - lat) > 0.5 or abs(rec_lon - lon) > 0.5:
            msg = "recorded rainfall covers a different location"
            raise UpstreamUnavailableError(
                msg, {"recorded": [rec_lon, rec_lat], "asked": [lon, lat]}
            )
        full = parse_open_meteo(self._doc, lon, lat)
        s, e = np.datetime64(start, "D"), np.datetime64(end, "D")
        keep = (full.days >= s) & (full.days <= e)
        if not keep.any():
            msg = "recorded rainfall does not cover the requested range"
            raise UpstreamUnavailableError(msg, {"start": str(start), "end": str(end)})
        return DailyRainfall(
            days=full.days[keep],
            mm=full.mm[keep],
            source=full.source + " [recorded]",
            grid_label=full.grid_label,
            latitude=lat,
            longitude=lon,
            attribution=full.attribution,
            fetched_live=False,
        )
