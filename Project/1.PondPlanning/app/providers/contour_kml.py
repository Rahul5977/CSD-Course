"""Contour-map parser for KML and KMZ uploads.

Adapter for an external file format, so it lives with the providers. It is
tolerant where the sample demands it and strict where guessing would be
dangerous:

* **Tolerant:** the root may be ``<Folder>`` rather than ``<kml><Document>``;
  namespaces are ignored by matching on local names; ``recover=True`` survives
  the objectify ``py:pytype`` attributes the sample carries.
* **Strict:** elevation is read by an *ordered* strategy — Z coordinate, then a
  whitelisted ``ExtendedData`` field, then the placemark ``<name>`` — and
  ``ID``-like fields are never accepted. When nothing works the parser raises
  rather than inventing a terrain model from row numbers (ADR 0011).

Only ``LineString`` placemarks are contours. ``Point`` placemarks in the sample
are duplicate labels and would double-weight the interpolation; a ``Polygon``
placemark is recorded as the area of interest if present.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections import Counter

import numpy as np
from lxml import etree

from app.domain.contours import (
    ELEVATION_STRATEGIES,
    ContourLine,
    ContourSet,
    ElevationSource,
)
from app.domain.errors import ElevationNotFoundError, UnsupportedInputError

#: Field names that may carry a contour's elevation. Matched case-insensitively
#: as a substring so ``elevation_m`` and ``CONTOUR_LEVEL`` both pass; ``ID``,
#: ``OBJECTID`` and ``FID`` never do.
_ELEVATION_FIELD = re.compile(r"(elev|contour|level|height|altitude|^z$)", re.IGNORECASE)
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def _local(element: etree._Element) -> str:
    return etree.QName(element).localname


def _child_text(element: etree._Element, local_name: str) -> str | None:
    for child in element:
        if isinstance(child.tag, str) and _local(child) == local_name and child.text:
            return child.text.strip()
    return None


def _parse_coordinates(text: str) -> np.ndarray:
    """Parse a KML ``<coordinates>`` block into an (n, 3) array; z is NaN when absent."""
    rows: list[tuple[float, float, float]] = []
    for token in text.split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        lon, lat = float(parts[0]), float(parts[1])
        z = float(parts[2]) if len(parts) > 2 and parts[2] != "" else float("nan")
        rows.append((lon, lat, z))
    return np.array(rows, dtype=np.float64).reshape(-1, 3)


def _elevation_from_z(coords: np.ndarray) -> float | None:
    """Strategy 1: a constant Z along the whole line is a contour elevation."""
    z = coords[:, 2]
    if z.size == 0 or np.isnan(z).any():
        return None
    if float(np.ptp(z)) > 1e-6:
        return None  # a 3-D track, not a contour
    return float(z[0])


def _elevation_from_extended_data(placemark: etree._Element) -> float | None:
    """Strategy 2: a whitelisted ``Data``/``SimpleData`` field."""
    for element in placemark.iter():
        if not isinstance(element.tag, str):
            continue
        local = _local(element)
        if local not in {"Data", "SimpleData"}:
            continue
        name = element.get("name") or ""
        if not _ELEVATION_FIELD.search(name):
            continue
        value = element.text if local == "SimpleData" else _child_text(element, "value")
        if value and _NUMBER.match(value.strip()):
            return float(value)
    return None


def _elevation_from_name(placemark: etree._Element) -> float | None:
    """Strategy 3: the placemark name is itself the number."""
    name = _child_text(placemark, "name")
    if name and _NUMBER.match(name):
        return float(name)
    return None


def _unwrap_kmz(payload: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".kml")]
        if not names:
            msg = "KMZ archive contains no .kml document"
            raise UnsupportedInputError(msg, {"entries": archive.namelist()[:20]})
        # doc.kml is the conventional entry; otherwise take the first.
        chosen = next((n for n in names if n.lower().endswith("doc.kml")), names[0])
        return archive.read(chosen)


def parse_contours(payload: bytes, filename: str = "upload.kml") -> ContourSet:
    """Parse a KML/KMZ contour map into a :class:`ContourSet`.

    Args:
        payload: Raw file bytes.
        filename: Used only to recognise ``.kmz``; a zip signature is also honoured.

    Raises:
        UnsupportedInputError: Not XML, or no ``LineString`` placemarks at all.
        ElevationNotFoundError: Lines exist but no strategy could read an elevation.
    """
    if filename.lower().endswith(".kmz") or payload[:2] == b"PK":
        payload = _unwrap_kmz(payload)

    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False, no_network=True)
    try:
        root = etree.fromstring(payload, parser)
    except etree.XMLSyntaxError as exc:
        msg = "upload is not well-formed XML"
        raise UnsupportedInputError(msg, {"reason": str(exc)}) from exc
    if root is None:
        msg = "upload is empty or not XML"
        raise UnsupportedInputError(msg)

    lines: list[ContourLine] = []
    aoi: np.ndarray | None = None
    texts: list[str] = []
    counts: Counter[str] = Counter()
    skipped = 0
    linestrings_seen = 0

    for placemark in root.iter():
        if not isinstance(placemark.tag, str) or _local(placemark) != "Placemark":
            continue
        for text_tag in ("name", "description"):
            text = _child_text(placemark, text_tag)
            if text and not _NUMBER.match(text):
                texts.append(text)

        geometry = next(
            (
                g
                for g in placemark.iter()
                if isinstance(g.tag, str) and _local(g) in {"LineString", "Polygon", "Point"}
            ),
            None,
        )
        if geometry is None:
            continue
        kind = _local(geometry)
        coordinates = next(
            (c for c in geometry.iter() if isinstance(c.tag, str) and _local(c) == "coordinates"),
            None,
        )
        if coordinates is None or not coordinates.text:
            continue
        coords = _parse_coordinates(coordinates.text)

        if kind == "Polygon":
            if aoi is None and coords.shape[0] >= 4:
                aoi = coords[:, :2].copy()
            continue
        if kind != "LineString":
            continue

        linestrings_seen += 1
        if coords.shape[0] < 2:
            skipped += 1
            continue

        elevation, source = _read_elevation(placemark, coords)
        if elevation is None or source is None:
            skipped += 1
            continue
        counts[source] += 1
        lines.append(ContourLine(elevation=elevation, coords=coords[:, :2].copy(), source=source))

    if linestrings_seen == 0:
        msg = "no LineString contours found in the upload"
        raise UnsupportedInputError(msg, {"hint": "contours must be LineString placemarks"})
    if not lines:
        msg = "no elevation could be read from any contour"
        raise ElevationNotFoundError(
            msg,
            {"strategies_tried": list(ELEVATION_STRATEGIES), "linestrings": linestrings_seen},
        )

    dominant: ElevationSource = counts.most_common(1)[0][0]  # type: ignore[assignment]
    lines.sort(key=lambda line: line.elevation)
    return ContourSet(
        lines=tuple(lines),
        elevation_source=dominant,
        aoi=aoi,
        metadata_text="\n".join(texts),
        skipped=skipped,
        strategy_counts=dict(counts),
    )


def _read_elevation(
    placemark: etree._Element, coords: np.ndarray
) -> tuple[float | None, ElevationSource | None]:
    """Apply the strategies in order and report which one answered."""
    z = _elevation_from_z(coords)
    if z is not None:
        return z, "z_coordinate"
    extended = _elevation_from_extended_data(placemark)
    if extended is not None:
        return extended, "extended_data"
    named = _elevation_from_name(placemark)
    if named is not None:
        return named, "placemark_name"
    return None, None
