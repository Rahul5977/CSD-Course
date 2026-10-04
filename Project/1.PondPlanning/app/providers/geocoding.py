"""Reverse geocoding — a place name for an area, derived from its own centroid.

The demo village is never named in code. When an upload is analysed, the
system asks OpenStreetMap's Nominatim what settlement the centroid falls in
and uses that; if the network is unavailable the village is named by its
coordinates and the result says so. Standard library only: one GET with a
five-second timeout does not justify an HTTP client dependency.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "pond-planner/0.1 (university assignment; rahul.raj9237@gmail.com)"


@dataclass(frozen=True, slots=True)
class PlaceName:
    """What the geocoder said about a point."""

    name: str
    district: str | None
    state: str | None
    state_code: str | None
    source: str


def reverse_geocode(lon: float, lat: float, *, timeout_s: float = 5.0) -> PlaceName | None:
    """Return the settlement at a point, or ``None`` if the lookup fails."""
    query = urllib.parse.urlencode({"lon": lon, "lat": lat, "format": "jsonv2", "zoom": 14})
    request = urllib.request.Request(
        f"{NOMINATIM}?{query}", headers={"User-Agent": USER_AGENT, "Accept-Language": "en"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("reverse geocode failed", extra={"reason": str(exc)})
        return None
    address = payload.get("address", {})
    name = next(
        (
            address[key]
            for key in ("village", "hamlet", "town", "suburb", "city", "county")
            if address.get(key)
        ),
        None,
    )
    if not name:
        return None
    return PlaceName(
        name=str(name),
        district=address.get("state_district") or address.get("county"),
        state=address.get("state"),
        state_code=(address.get("ISO3166-2-lvl4") or "").split("-")[-1] or None,
        source="OpenStreetMap Nominatim",
    )


def fallback_name(lon: float, lat: float) -> str:
    """Deterministic name when no geocoder answer is available."""
    return f"AOI {lat:.4f}N {lon:.4f}E"
