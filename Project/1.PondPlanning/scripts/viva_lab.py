# ruff: noqa: E501, D102, D103, D107, E741
"""Viva lab: run the terrain -> hydrology -> siting chain stage by stage and print what each stage did.

    uv run python scripts/viva_lab.py                      # the sample map, offline (no water mask)
    uv run python scripts/viva_lab.py --water              # also read the GLO-30 water mask (network)
    uv run python scripts/viva_lab.py --toy                # 5x5 toy DEM: print D8 codes, accumulation, BFS

Every number comes from the same engine functions the API calls (no copies of the algorithms here).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from app.domain.geo import GridSpec
from app.domain.raster import Raster
from app.engines.hydrology.catchment import delineate, upstream_mask
from app.engines.hydrology.conditioning import fill_depressions
from app.engines.hydrology.flow import build_flow_model, edge_fed, stream_mask
from app.engines.hydrology.siting import rank_sites
from app.engines.hydrology.streams import extract_links
from app.engines.suitability.ahp import DEFAULT_CRITERIA, DEFAULT_MATRIX, ahp_weights
from app.engines.terrain.derived import topographic_wetness_index
from app.engines.terrain.interpolate import contours_to_dem
from app.engines.terrain.surfaces import slope_degrees
from app.providers.contour_kml import parse_contours
from app.providers.dem_provenance import infer_provenance

ARROW = {0: "o", 1: "→", 2: "↘", 4: "↓", 8: "↙", 16: "←", 32: "↖", 64: "↑", 128: "↗"}


class Clock:
    """Prints one line per stage with its wall time."""

    def __init__(self) -> None:
        self.t = time.perf_counter()

    def lap(self, label: str, detail: str = "") -> None:
        now = time.perf_counter()
        print(f"  {label:<38} {1000 * (now - self.t):8.1f} ms   {detail}")
        self.t = now


def toy() -> None:
    """A 5x5 DEM with a pit, small enough to check by hand."""
    z = np.array(
        [
            [9, 8, 7, 8, 9],
            [8, 6, 5, 6, 8],
            [7, 5, 2, 5, 7],  # 2 is a pit: every neighbour is higher
            [8, 6, 4, 6, 8],
            [9, 8, 3, 8, 9],  # the valley drains out through the bottom edge at (4, 2)
        ],
        dtype=float,
    )
    dem = Raster(GridSpec(epsg=32644, x_min=0, y_max=150, cell_size=30, rows=5, cols=5), z)
    cond = fill_depressions(dem)
    print("raw DEM:\n", z)
    print("filled (Priority-Flood + eps):\n", cond.filled.data.round(4))
    print(f"cells raised: {cond.cells_filled}, max fill {cond.max_fill_m:.4f} m")
    model = build_flow_model(cond.filled)
    print("D8 directions:")
    for row in model.direction:
        print("   ", " ".join(ARROW[int(v)] for v in row))
    print("accumulation (cells draining through each cell, itself included):\n", model.accumulation)
    print(
        "edge-fed (catchment touches the map edge):\n",
        edge_fed(cond.filled, model.receiver).astype(int),
    )
    mask = upstream_mask(model, 4, 2)
    print(
        "reverse-BFS catchment of outlet (4,2):\n", mask.astype(int), f"= {int(mask.sum())} cells"
    )


def sample(with_water: bool) -> None:
    root = Path(__file__).resolve().parents[1]
    payload = (root / "data/samples/contours_1m.kml").read_bytes()
    clock = Clock()
    print("\nSample map: data/samples/contours_1m.kml")
    contours = parse_contours(payload, "contours_1m.kml")
    clock.lap(
        "parse KML", f"{len(contours.lines)} contours, elevation from {contours.elevation_source}"
    )
    prov = infer_provenance(contours.metadata_text, default_resolution_m=30.0)
    clock.lap("infer provenance", f"{prov.source}, {prov.native_resolution_m:g} m native")
    tin = contours_to_dem(contours, floor_m=prov.native_resolution_m)
    g = tin.raster.grid
    clock.lap(
        "TIN -> DEM",
        f"EPSG:{tin.epsg}, spacing {tin.contour_spacing_m:.1f} m -> cell {tin.resolution_m:.1f} m, "
        f"{g.rows}x{g.cols} = {g.rows * g.cols} cells",
    )
    water = None
    if with_water:
        from app.providers.copernicus_dem import read_glo30_water

        water = read_glo30_water(g)
        clock.lap(
            "GLO-30 water body mask",
            "unavailable" if water is None else f"{int(water.sum())} water cells",
        )
    slope = slope_degrees(tin.raster)
    clock.lap("Horn slope", f"mean {np.nanmean(slope.data):.2f} deg")
    cond = fill_depressions(tin.raster)
    clock.lap(
        "Priority-Flood + eps", f"{cond.cells_filled} cells raised, max {cond.max_fill_m:.2f} m"
    )
    model = build_flow_model(cond.filled)
    clock.lap(
        "D8 + accumulation sweep",
        f"max upstream {model.accumulation.max() * g.cell_area / 1e4:.0f} ha",
    )
    twi = topographic_wetness_index(tin.raster, model.accumulation)
    streams = stream_mask(model, 50_000.0)
    links = extract_links(model, streams)
    clock.lap(
        "TWI, streams (5 ha), Strahler",
        f"{int(streams.sum())} stream cells, {len(links)} links, max order {max(l.order for l in links)}",
    )
    siting = rank_sites(model, slope.data, twi.data, streams, water=water)
    clock.lap(
        "rank sites (exclusions, score, NMS)",
        f"{siting.considered} eligible of {int(streams.sum())}; river/belt excluded {siting.river_cells_excluded}, "
        f"edge-fed excluded {siting.edge_fed_excluded}",
    )
    best = siting.candidates[0]
    c = delineate(model, best.row, best.col, radius_m=150, min_area_m2=20_000)
    clock.lap(
        "reverse-BFS catchment of site #1",
        f"{c.area_m2 / 1e4:.1f} ha, longest path {c.longest_flow_path_m:.0f} m, relief {c.relief_m:.1f} m",
    )
    print("\n  weights used by siting:", {k: round(v, 3) for k, v in siting.weights.items()})
    ahp = ahp_weights(DEFAULT_MATRIX, DEFAULT_CRITERIA)
    print(
        "  AHP eigenvector weights:",
        {k: round(v, 3) for k, v in ahp.weights.items()},
        f"lambda_max {ahp.lambda_max:.4f}, CR {ahp.consistency_ratio:.4f}",
    )
    print("\n  rank  score  area_ha  slope%   TWI   imp_m   criteria")
    for i, s in enumerate(siting.candidates, 1):
        crit = " ".join(f"{k[:4]}={v:.2f}" for k, v in s.criteria_scores.items())
        print(
            f"  {i:>4}  {s.score:.3f}  {s.upstream_area_m2 / 1e4:7.1f}  {s.slope_pct:6.2f}  "
            f"{s.twi:5.1f}  {s.impoundment_efficiency_m:5.2f}   {crit}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--toy", action="store_true")
    parser.add_argument("--water", action="store_true")
    args = parser.parse_args()
    toy() if args.toy else sample(args.water)
