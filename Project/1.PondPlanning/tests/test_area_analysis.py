"""Phase 3: a land area selected on the map → pond site, catchment, terrain.

The tile reader is pointed at a local directory holding a synthetic GLO-30
tile — a V-shaped valley draining south, with its head and both side ridges
*inside* the selected box — so the whole route runs offline and the expected
answer is known: the pond site lies on the valley axis, its catchment drains
from upslope (north) and is complete (no cell on the box edge).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from app.core.config import get_settings
from app.domain.errors import AreaOutOfRangeError
from app.engines.terrain.adapters import (
    ProviderTileAdapter,
    box_area_km2,
    check_area,
    grid_for_bounds,
)
from app.jobs.context import get_context
from app.providers.copernicus_dem import read_glo30, tile_name, tile_url, tiles_for

TILE_LAT, TILE_LON = 10, 78
AXIS_LON = 78.505  # valley axis
BOX = (78.49, 10.40, 78.52, 10.43)  # ~3.3 x 3.3 km, straddles the axis
RIDGE = 0.01  # side ridges at axis ± 0.01°, inside the box
HEAD_LAT = 10.425  # valley head (divide) inside the box


def _write_valley_tile(base: Path) -> None:
    """A 1° tile at 6″ (~185 m) — coarse, but the surface is smooth and bilinear is exact on it."""
    name = tile_name(TILE_LAT, TILE_LON)
    (base / name).mkdir(parents=True)
    n = 600
    step = 1.0 / n
    lon = TILE_LON + (np.arange(n) + 0.5) * step
    lat = TILE_LAT + 1 - (np.arange(n) + 0.5) * step
    glon, glat = np.meshgrid(lon, lat)
    # Cross-section: 400 m/° (~3.6 %) up to ridges 0.01° either side of the axis, then
    # down the outer flanks at ~22 % — steeper than the 15 % siting limit, so the only
    # plausible pond sites are in the valley. Long profile: 200 m/° (~1.8 %) down to
    # the south from a valley head at HEAD_LAT.
    dx = np.abs(glon - AXIS_LON)
    cross = np.where(dx <= RIDGE, dx, RIDGE - 60.0 * (dx - RIDGE))
    z = 300.0 + 400.0 * cross + 200.0 * (HEAD_LAT - np.abs(glat - HEAD_LAT) - TILE_LAT)
    with rasterio.open(
        base / name / f"{name}.tif",
        "w",
        driver="GTiff",
        width=n,
        height=n,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(TILE_LON, TILE_LAT + 1, step, step),
        nodata=-32767.0,
    ) as dst:
        dst.write(z.astype("float32"), 1)


@pytest.fixture
def tiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Local tile directory wired in as the DEM base URL."""
    _write_valley_tile(tmp_path)
    monkeypatch.setenv("POND_DEM_TILE_BASE_URL", str(tmp_path))
    get_settings.cache_clear()
    get_context.cache_clear()
    return tmp_path


def test_tile_naming_follows_the_published_scheme() -> None:
    assert tile_name(21, 81) == "Copernicus_DSM_COG_10_N21_00_E081_00_DEM"
    assert tile_name(-1, -75) == "Copernicus_DSM_COG_10_S01_00_W075_00_DEM"
    assert tiles_for((80.9, 20.9, 81.1, 21.1)) == [
        tile_name(20, 80),
        tile_name(20, 81),
        tile_name(21, 80),
        tile_name(21, 81),
    ]
    assert tile_url("https://h", "T").startswith("/vsicurl/https://h/T/T.tif")
    assert tile_url("/data", "T") == "/data/T/T.tif"


def test_area_is_measured_in_metres_and_bounded() -> None:
    assert box_area_km2(BOX) == pytest.approx(3.28 * 3.28, rel=0.03)
    assert check_area(BOX, 0.25, 25.0) > 0
    with pytest.raises(AreaOutOfRangeError):
        check_area((78.5, 10.4, 78.501, 10.401), 0.25, 25.0)  # ~0.01 km²
    with pytest.raises(AreaOutOfRangeError):
        check_area((78.0, 10.0, 78.2, 10.2), 0.25, 25.0)  # ~480 km²


def test_grid_zone_is_derived_from_the_selection() -> None:
    assert grid_for_bounds(BOX, 30.0).epsg == 32644
    assert grid_for_bounds((-75.1, -1.1, -75.0, -1.0), 30.0).epsg == 32718


def test_adapter_reads_and_warps_the_tile(tiles: Path) -> None:
    product = ProviderTileAdapter(BOX, read=lambda b, g: read_glo30(b, g, str(tiles))).produce()
    data = product.raster.data
    assert product.working_resolution_m == 30.0
    assert not np.isnan(data).any()
    # Crest: 300 + 400 x 0.01 + 200 x 0.425 = 389 m; floor falls 5 m to the south edge.
    assert data.max() < 389.5
    assert data.min() < 300 + 200 * 0.40 + 1
    assert product.details["elevation_source"] == "dem_raster"
    assert "GLO-30" in product.provenance.source
    assert any(code == "surface_model" for code, _, _ in product.warnings)
    assert product.details["gap_fraction"] == 0.0, "the grid's corners are read, not gap-filled"


def test_selected_area_yields_site_catchment_and_terrain(client: TestClient, tiles: Path) -> None:
    response = client.post("/api/v1/analyzeArea", json={"bbox": list(BOX)})
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert status["status"] == "succeeded", status
    result = client.get(f"/api/v1/analysis/results/contour/{job_id}").json()

    assert result["source_file"] == "map selection"
    assert result["terrain"]["provider"] == "copernicus_glo30"
    assert result["contour_interval"] is None
    assert result["utm_epsg"] == 32644
    site = result["suggested_pond_location"]
    w, s, e, n = BOX
    assert w <= site["lon"] <= e and s <= site["lat"] <= n
    assert abs(site["lon"] - AXIS_LON) < 0.003, "the site sits on the valley axis"
    catchment = result["catchment"]
    assert catchment is not None and catchment["area"]["value"] > 5.0
    ring = np.array(catchment["geojson"]["features"][0]["geometry"]["coordinates"][0])
    assert ring[:, 1].max() > site["lat"], "the catchment drains from upslope (north)"
    assert ring[:, 1].max() < HEAD_LAT + 0.002, "…and stops at the valley head"
    codes = {w["code"] for w in result["warnings"]}
    assert "catchment_truncated" not in codes, "complete-catchment constraint"
    assert result["siting"]["catchments_complete"] is True
    # Village created from the selection; its boundary is the box.
    village = client.get(f"/api/v1/villages/{result['village_id']}").json()
    assert village["id"] == result["village_id"]


def test_out_of_range_area_is_a_stable_422(client: TestClient) -> None:
    response = client.post("/api/v1/analyzeArea", json={"bbox": [78.0, 10.0, 78.3, 10.3]})
    assert response.status_code == 422
    assert response.json()["code"] == "area_out_of_range"


def test_malformed_box_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/analyzeArea", json={"bbox": [78.5, 10.4, 78.4, 10.5]})
    assert response.status_code == 422
