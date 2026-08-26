"""Build export artifacts from a saved recommendation's design payload.

- **GeoJSON**: the pond point, its footprint and the catchment polygon.
- **CSV**: the bill of quantities and headline figures, one row per item.
- **PDF**: a one-page proposal sheet (reportlab) — the thing that attaches
  to an MGNREGA work proposal.
"""

from __future__ import annotations

import csv
import io
import json
import math
from typing import Any

from app.repositories.records import RecommendationRecord


def _q(d: dict[str, Any], *path: str) -> Any:
    cur: Any = d
    for key in path:
        cur = cur.get(key, {}) if isinstance(cur, dict) else {}
    return cur


def export_geojson(rec: RecommendationRecord) -> bytes:
    """Pond point + footprint + catchment as a FeatureCollection."""
    design = rec.payload
    dims = design.get("dimensions", {})
    length = float(_q(dims, "top_length").get("value", 0.0) or 0.0)
    width = float(_q(dims, "top_width").get("value", 0.0) or 0.0)
    d_lat = width / 2 / 111_320
    d_lon = length / 2 / (111_320 * math.cos(math.radians(rec.lat)))
    features: list[dict[str, Any]] = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [rec.lon, rec.lat]},
            "properties": {
                "kind": "pond_location",
                "recommendation_id": str(rec.id),
                "status": rec.status,
            },
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [rec.lon - d_lon, rec.lat - d_lat],
                        [rec.lon + d_lon, rec.lat - d_lat],
                        [rec.lon + d_lon, rec.lat + d_lat],
                        [rec.lon - d_lon, rec.lat + d_lat],
                        [rec.lon - d_lon, rec.lat - d_lat],
                    ]
                ],
            },
            "properties": {
                "kind": "pond_footprint",
                "top_length_m": length,
                "top_width_m": width,
                "depth_m": rec.depth_m,
            },
        },
    ]
    catchment = design.get("catchment", {}).get("geojson", {}).get("features", [])
    for feature in catchment:
        if feature.get("properties", {}).get("kind") == "catchment":
            features.append(feature)
    doc = {"type": "FeatureCollection", "features": features, "crs": "EPSG:4326"}
    return json.dumps(doc).encode()


def _rows(rec: RecommendationRecord) -> list[tuple[str, str, str]]:
    d = rec.payload
    boq = d.get("bill_of_quantities", {})
    rows = [
        ("village", rec.village_name, ""),
        ("location", f"{rec.lat:.5f} N, {rec.lon:.5f} E", "EPSG:4326"),
        ("status", rec.status, ""),
        ("confidence", rec.confidence, str(d.get("confidence_rationale", ""))),
    ]
    for label, q in [
        ("catchment_area", _q(d, "catchment", "area")),
        ("rainfall_75pct_dependable", _q(d, "rainfall_summary", "dependable_75")),
        ("runoff_scs_cn_75pct", _q(d, "runoff", "recommended", "annual_runoff_volume")),
        ("gross_storage", d.get("gross_storage", {})),
        ("live_storage", d.get("live_storage", {})),
        ("depth", _q(d, "dimensions", "depth")),
        ("top_length", _q(d, "dimensions", "top_length")),
        ("top_width", _q(d, "dimensions", "top_width")),
        ("fill_reliability", d.get("reliability", {})),
        ("excavation_volume", boq.get("excavation_volume", {})),
        ("embankment_volume", boq.get("embankment_volume", {})),
        ("indicative_cost", boq.get("indicative_cost", {})),
    ]:
        if q:
            rows.append(
                (label, str(q.get("display", q.get("value", ""))), str(q.get("method", "")))
            )
    rows.append(("cost_basis", str(boq.get("cost_basis", "")), ""))
    return rows


def export_csv(rec: RecommendationRecord) -> bytes:
    """Headline figures and bill of quantities."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["item", "value", "method"])
    writer.writerows(_rows(rec))
    return buffer.getvalue().encode()


def export_pdf(rec: RecommendationRecord) -> bytes:
    """One-page proposal sheet."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _width, height = A4
    y = height - 25 * mm
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(20 * mm, y, f"Pond proposal — {rec.village_name}")
    y -= 8 * mm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        20 * mm,
        y,
        f"Recommendation {rec.id} · status {rec.status} · created by {rec.created_by} · "
        f"{rec.created_at:%Y-%m-%d}",
    )
    y -= 10 * mm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(20 * mm, y, "Item")
    pdf.drawString(80 * mm, y, "Value")
    pdf.drawString(140 * mm, y, "Method")
    y -= 6 * mm
    pdf.setFont("Helvetica", 9)
    for item, value, method in _rows(rec):
        if y < 25 * mm:
            pdf.showPage()
            y = height - 25 * mm
            pdf.setFont("Helvetica", 9)
        pdf.drawString(20 * mm, y, item.replace("_", " "))
        pdf.drawString(80 * mm, y, value[:40])
        pdf.drawString(140 * mm, y, method[:45])
        y -= 5.5 * mm
    y -= 6 * mm
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(
        20 * mm,
        y,
        "Planning-grade estimate from a contour-interpolated DEM (~30 m source), "
        "reanalysis rainfall and satellite land cover.",
    )
    y -= 4 * mm
    pdf.drawString(
        20 * mm,
        y,
        "Every figure carries its uncertainty band. Confirm with a ground survey before sanction.",
    )
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


EXPORTERS = {
    "geojson": (export_geojson, "application/geo+json"),
    "csv": (export_csv, "text/csv"),
    "pdf": (export_pdf, "application/pdf"),
}
