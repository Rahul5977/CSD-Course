"""Cross-check the two terrain sources on the same ground: contour KML vs Copernicus GLO-30.

The Phase 2 path builds its DEM from the uploaded contours (SRTM-derived);
the Phase 3 map-selection path reads Copernicus GLO-30. Both feed the same
hydrology chain. This script puts GLO-30 on the *exact* grid the KML path
builds for the sample, runs the chain on each, and compares:

* elevation — bias, RMSE and correlation (after removing the mean offset,
  since the two datums/epochs differ);
* stream networks — agreement of the channel cells, with a one-cell tolerance;
* catchment area at the same outlets — the KML path's ranked sites,
  each snapped on its own model;
* the suggested site — distance between the two sources' top picks.

Writes ``docs/figures/p9-dem-crosscheck.md`` and ``p9-dem-crosscheck.png``.
Needs the network (reads the public GLO-30 tile). Run: ``make crosscheck``.
"""

# ruff: noqa: RUF001, E501  -- report text: typographic minus/times/dashes, long table rows
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import binary_dilation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.domain.errors import ValidationError  # noqa: E402
from app.domain.raster import Raster  # noqa: E402
from app.engines.hydrology.catchment import delineate  # noqa: E402
from app.engines.hydrology.conditioning import fill_depressions  # noqa: E402
from app.engines.hydrology.flow import FlowModel, build_flow_model, stream_mask  # noqa: E402
from app.engines.hydrology.siting import SitingResult, rank_sites  # noqa: E402
from app.engines.terrain.adapters import ContourKMLAdapter  # noqa: E402
from app.engines.terrain.derived import topographic_wetness_index  # noqa: E402
from app.engines.terrain.surfaces import slope_degrees  # noqa: E402
from app.providers.copernicus_dem import read_glo30, read_glo30_water  # noqa: E402

SAMPLE = ROOT / "data" / "samples" / "contours_1m.kml"
OUT = ROOT / "docs" / "figures"
STREAM_M2 = 50_000.0


def chain(
    dem: Raster, water: np.ndarray | None = None
) -> tuple[FlowModel, np.ndarray, SitingResult]:
    """The production chain: fill, D8, streams, siting (with mapped water when given)."""
    model = build_flow_model(fill_depressions(dem).filled)
    streams = stream_mask(model, STREAM_M2)
    slope = slope_degrees(dem).data
    twi = topographic_wetness_index(dem, model.accumulation).data
    return model, streams, rank_sites(model, slope, twi, streams, water=water)


def main() -> None:
    """Build both DEMs on one grid, run the chain on each, write the table and figure."""
    kml = ContourKMLAdapter(SAMPLE.read_bytes(), SAMPLE.name, default_floor_m=10.0).produce()
    grid = kml.raster.grid
    west, south, east, north = kml.details["bounds_lonlat"]
    glo = read_glo30((west, south, east, north), grid)

    a, b = kml.raster.data, glo.data
    ok = ~np.isnan(a) & ~np.isnan(b)
    diff = b[ok] - a[ok]
    bias = float(diff.mean())
    rmse_raw = float(np.sqrt(np.mean(diff**2)))
    rmse_detrended = float(np.sqrt(np.mean((diff - bias) ** 2)))
    corr = float(np.corrcoef(a[ok], b[ok])[0, 1])

    m_kml, s_kml, site_kml = chain(kml.raster)
    water = read_glo30_water(grid)
    m_glo, s_glo, site_glo = chain(glo, water)
    tol = np.ones((3, 3), dtype=bool)
    hit_kml = float((s_kml & binary_dilation(s_glo, tol)).sum() / max(s_kml.sum(), 1))
    hit_glo = float((s_glo & binary_dilation(s_kml, tol)).sum() / max(s_glo.sum(), 1))

    # Major channels only (≥ 50 ha upstream), two-cell tolerance: the network a
    # planner would recognise on the satellite image.
    big_k = m_kml.upstream_area_m2() >= 500_000
    big_g = m_glo.upstream_area_m2() >= 500_000
    tol2 = np.ones((5, 5), dtype=bool)
    major_hit = float((big_k & binary_dilation(big_g, tol2)).sum() / max(big_k.sum(), 1))
    outlet_k = float(m_kml.upstream_area_m2().max() / 1e4)
    outlet_g = float(m_glo.upstream_area_m2().max() / 1e4)

    rows = []
    for rank, c in enumerate(site_kml.candidates, start=1):
        ca = delineate(m_kml, c.row, c.col, radius_m=150, min_area_m2=20_000).area_m2 / 1e4
        try:
            cb = delineate(m_glo, c.row, c.col, radius_m=150, min_area_m2=20_000).area_m2 / 1e4
        except ValidationError:
            cb = float("nan")
        rows.append((rank, ca, cb))

    top_distance_m = float("nan")
    if site_kml.candidates and site_glo.candidates:
        ka, gb = site_kml.candidates[0], site_glo.candidates[0]
        top_distance_m = float(np.hypot(ka.row - gb.row, ka.col - gb.col) * grid.cell_size)

    # ---- figure --------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), constrained_layout=True)
    vmin, vmax = np.nanpercentile(np.concatenate([a[ok], b[ok]]), [1, 99])
    axes[0].imshow(a, cmap="terrain", vmin=vmin, vmax=vmax)
    axes[0].imshow(np.where(s_kml, 1, np.nan), cmap="Blues_r", interpolation="none")
    axes[0].set_title("Contour KML → TIN DEM, streams (5 ha)")
    axes[1].imshow(b, cmap="terrain", vmin=vmin, vmax=vmax)
    axes[1].imshow(np.where(s_glo, 1, np.nan), cmap="Blues_r", interpolation="none")
    axes[1].set_title("Copernicus GLO-30, same grid, streams (5 ha)")
    for ax, site in ((axes[0], site_kml), (axes[1], site_glo)):
        for i, c in enumerate(site.candidates):
            ax.plot(
                c.col,
                c.row,
                "o",
                ms=11 if i == 0 else 7,
                mfc="#2e7d32" if i == 0 else "#8bc34a",
                mec="white",
            )
        ax.set_xticks([])
        ax.set_yticks([])
    im = axes[2].imshow(b - a - bias, cmap="RdBu_r", vmin=-8, vmax=8)
    axes[2].set_title(f"GLO-30 − KML, offset {bias:+.1f} m removed (RMSE {rmse_detrended:.1f} m)")
    axes[2].set_xticks([])
    axes[2].set_yticks([])
    fig.colorbar(im, ax=axes[2], shrink=0.8, label="m")
    fig.savefig(OUT / "p9-dem-crosscheck.png", dpi=130)

    # ---- table ----------------------------------------------------------
    lines = [
        "# Terrain-source cross-check — contour KML vs Copernicus GLO-30",
        "",
        "Generated by `scripts/crosscheck_dem_sources.py` on the provided sample AOI "
        f"({grid.rows}×{grid.cols} cells at {grid.cell_size:g} m, EPSG:{grid.epsg}). "
        "Both DEMs run through the identical hydrology chain.",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Mean offset GLO-30 − KML | {bias:+.2f} m |",
        f"| RMSE (raw / offset removed) | {rmse_raw:.2f} m / {rmse_detrended:.2f} m |",
        f"| Pearson correlation of elevations | {corr:.3f} |",
        f"| KML channel cells within 1 cell of a GLO-30 channel | {hit_kml:.0%} |",
        f"| GLO-30 channel cells within 1 cell of a KML channel | {hit_glo:.0%} |",
        f"| Major channels (≥ 50 ha) of the KML path within 2 cells of GLO-30's | {major_hit:.0%} |",
        f"| Largest drainage area in the map, KML / GLO-30 | {outlet_k:,.0f} ha / {outlet_g:,.0f} ha |",
        f"| Distance between the two top-ranked sites | {top_distance_m:,.0f} m |",
        f"| Cells mapped as water by the GLO-30 water body mask | "
        f"{0 if water is None else int(water.sum())} |",
        "",
        "Catchment area at the KML path's ranked sites, each snapped on its own model:",
        "",
        "| Site | KML path (ha) | GLO-30 path (ha) | Difference |",
        "|---|---|---|---|",
    ]
    for rank, ca, cb in rows:
        pct = f"{100 * (cb - ca) / ca:+.0f} %" if np.isfinite(cb) else "no channel within 150 m"
        lines.append(f"| {rank} | {ca:.1f} | {cb:.1f} | {pct} |")
    lines += [
        "",
        "**Reading.** The two elevation sources agree as *surfaces*: after the datum "
        "offset the RMSE is within both products' stated relative accuracy and the "
        "correlation is high. They do not agree as *drainage*. The sample is very flat "
        "(mean slope ≈ 1.6°, 31 m of relief over 3 km), so a 2 m difference sends a "
        "10–30 ha flow path to the neighbouring hollow, and catchments at the small ranked "
        "sites differ by a factor of several. Only the total drainage agrees closely. "
        "On the floodplain GLO-30 has a flattened river surface (water-body editing), on "
        "which D8 splits the flow into parallel lines; the tile's water body mask is now "
        "read with the DEM and excluded from siting with the flood-belt buffer, so no "
        "site lands in the river. pysheds on the *same* DEM matched our catchments "
        "within 2–3 % (ADR 0015): the algorithm is not the uncertainty — **the source "
        "DEM is**. Hence the ±15–50 % band and confidence label on every catchment, the "
        "visible snap distance, and the report's statement that on flat land the outlet "
        "must be checked in the field before construction.",
        "",
        "![cross-check](p9-dem-crosscheck.png)",
    ]
    (OUT / "p9-dem-crosscheck.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
