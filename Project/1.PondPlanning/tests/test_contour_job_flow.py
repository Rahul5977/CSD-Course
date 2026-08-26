"""End-to-end through the API on the provided sample: upload → job → result → FR1 routes.

This is the walking skeleton's proof — the same code path Docker runs, with the
in-memory, inline and local adapters behind the ports.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import SAMPLE_KML

pytestmark = pytest.mark.skipif(not SAMPLE_KML.exists(), reason="sample map not present")


@pytest.fixture
def analysed(client: TestClient) -> tuple[TestClient, dict]:  # type: ignore[type-arg]
    """Upload the sample; the pipeline takes a couple of seconds in-process."""
    with SAMPLE_KML.open("rb") as handle:
        response = client.post(
            "/api/v1/analyzeContour",
            files={"file": (SAMPLE_KML.name, handle, "application/vnd.google-earth.kml+xml")},
        )
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert status["status"] == "succeeded", status
    result = client.get(f"/api/v1/jobs/{job_id}/result").json()["result"]
    result["job_id"] = job_id
    return client, result


def test_result_is_derived_from_the_upload(
    analysed: tuple[TestClient, dict],  # type: ignore[type-arg]
) -> None:
    _, result = analysed
    terrain = result["terrain"]
    assert terrain["provider"] == "contour_kml"
    assert result["elevation_source"] == "placemark_name"
    assert result["contour_count"] == 1355
    assert result["contour_interval"]["value"] == 1.0
    assert result["utm_epsg"] == 32644, "zone derived from the file's own centroid"
    # A 30 m grid with sigma=1 smoothing cannot hold an isolated 1 m low/high, so the
    # extremes sit a metre or two inside the contour range — and that is honest,
    # given SRTM's ±6 m relative accuracy.
    assert result["elevation_range"]["minimum"]["value"] == pytest.approx(267.0, abs=2.5)
    assert result["elevation_range"]["maximum"]["value"] == pytest.approx(298.0, abs=2.5)
    assert result["grid_resolution"]["value"] >= 30.0, "floored at the SRTM source resolution"
    assert "SRTM" in terrain["dem"]["source"]
    assert terrain["dem"]["native_resolution"]["value"] == 30.0
    layers = {layer["layer_id"] for layer in result["terrain"]["layers"]}
    assert layers >= {"satellite", "hillshade", "dem", "slope", "twi", "streams", "contours"}
    assert result["elevation_range"]["minimum"]["display"].endswith("%)")  # unit + band


def test_the_route_identifies_a_pond_site_and_its_catchment(
    analysed: tuple[TestClient, dict],  # type: ignore[type-arg]
) -> None:
    """The Phase 2 brief: 'identify a suitable pond location, estimate its catchment'."""
    client, result = analysed
    site = result["suggested_pond_location"]
    w, s, e, n = result["bounds"]
    assert w <= site["lon"] <= e and s <= site["lat"] <= n, "site lies inside the uploaded map"
    assert result["location_rationale"]
    sites = result["candidate_sites"]
    assert 1 <= len(sites) <= 5 and sites[0]["rank"] == 1
    assert sites[0]["score"]["value"] >= sites[-1]["score"]["value"]
    assert set(sites[0]["criteria"]) == {"upstream_area", "flatness", "wetness", "impoundment"}
    assert sum(result["siting"]["weights"].values()) == pytest.approx(1.0)

    catchment = result["catchment"]
    assert catchment["area"]["unit"] == "ha" and catchment["area"]["value"] > 1.0
    assert catchment["area"]["uncertainty_pct"] >= 15.0
    assert catchment["flow_routing"].startswith("D8")
    assert catchment["geojson"]["features"][0]["geometry"]["type"] in {"Polygon", "MultiPolygon"}
    assert catchment["snap_distance"]["unit"] == "m"
    # The full payload is also served at the documented result route.
    assert client.get(f"/api/v1/analysis/results/contour/{result['job_id']}").status_code == 200


def test_click_to_catchment_and_terrain_layers(
    analysed: tuple[TestClient, dict],  # type: ignore[type-arg]
) -> None:
    """FR4 from the API: click a point → job → catchment polygon; FR2 contours; streams; derived."""
    client, result = analysed
    village_id = result["village_id"]
    lon, lat = result["suggested_pond_location"]["lon"], result["suggested_pond_location"]["lat"]
    accepted = client.post(
        "/api/v1/analysis/catchment",
        json={"village_id": village_id, "pour_point": {"lon": lon, "lat": lat}},
    )
    assert accepted.status_code == 202, accepted.text
    job_id = accepted.json()["job_id"]
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "succeeded"
    catchment = client.get(f"/api/v1/analysis/results/catchment/{job_id}").json()
    assert catchment["area"]["value"] == pytest.approx(
        result["catchment"]["area"]["value"], rel=0.01
    )
    assert catchment["snap_distance"]["value"] < 100

    contours = client.get(f"/api/v1/terrain/{village_id}/contours?interval=5").json()
    assert contours["levels"] >= 4
    assert contours["vertices_after_simplification"] <= contours["vertices_before_simplification"]
    assert contours["geojson"]["features"][0]["properties"]["elevation"] % 5 == 0

    siting = client.get(f"/api/v1/villages/{village_id}/siting").json()
    assert siting["candidate_sites"][0]["rank"] == 1 and siting["location_rationale"]

    streams = client.get(f"/api/v1/terrain/{village_id}/streams").json()
    assert streams["strahler_max_order"] >= 1 and streams["geojson"]["features"]

    slope = client.get(f"/api/v1/terrain/{village_id}/derived/slope").json()
    assert slope["algorithm"].startswith("Horn")
    assert "colormap_name=viridis" in slope["layer"]["tile_url_template"]
    twi = client.get(f"/api/v1/terrain/{village_id}/derived/twi").json()
    assert "p98" in twi["statistics"]


def test_village_routes_serve_the_analysed_area(
    analysed: tuple[TestClient, dict],  # type: ignore[type-arg]
) -> None:
    """FR1 routes, all real, all reading what the job wrote."""
    client, result = analysed
    village_id = result["village_id"]

    listing = client.get("/api/v1/villages").json()
    assert any(item["id"] == village_id for item in listing["items"])

    village = client.get(f"/api/v1/villages/{village_id}").json()
    assert village["utm_epsg"] == 32644
    assert 700 < village["area"]["value"] < 1000, "≈ 8.5 km² AOI in hectares"
    assert village["area"]["unit"] == "ha"

    summary = client.get(f"/api/v1/villages/{village_id}/summary").json()
    # Contour levels span 31 m; a 30 m grid loses the single-cell extremes.
    assert 24.0 < summary["elevation"]["relief"]["value"] <= 31.0
    assert summary["mean_slope"]["unit"] == "deg"
    assert any(w["code"] == "boundary_is_upload_extent" for w in summary["warnings"])

    imagery = client.get(f"/api/v1/villages/{village_id}/imagery").json()
    assert "{z}" in imagery["tile_url_template"]

    dem = client.get(f"/api/v1/terrain/{village_id}/dem").json()
    assert dem["crs"] == "EPSG:32644"
    layers = client.get(f"/api/v1/terrain/{village_id}/layers").json()["layers"]
    hillshade = next(layer for layer in layers if layer["layer_id"] == "hillshade")
    assert "/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png" in hillshade["tile_url_template"]

    for path in (
        f"/api/v1/villages/{village_id}",
        f"/api/v1/villages/{village_id}/summary",
        f"/api/v1/terrain/{village_id}/dem",
    ):
        assert "X-Fixture-Data" not in client.get(path).headers, path


def test_unknown_village_is_404_problem(client: TestClient) -> None:
    response = client.get("/api/v1/villages/3f2a9c1e-5b7d-4e8a-9c1f-2d6b8e4a7c93/summary")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_wrong_extension_is_rejected_before_any_work(client: TestClient) -> None:
    response = client.post("/api/v1/analyzeContour", files={"file": ("notes.txt", b"hello")})
    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_input"


def test_a_map_without_elevations_fails_the_job_honestly(client: TestClient) -> None:
    """The ID-decoy case surfaces as a failed job with the domain code, not a 500."""
    kml = (
        b'<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark>'
        b'<ExtendedData><SchemaData><SimpleData name="ID">3</SimpleData></SchemaData>'
        b"</ExtendedData><LineString><coordinates>81,21 81.001,21</coordinates></LineString>"
        b"</Placemark></Document></kml>"
    )
    accepted = client.post("/api/v1/analyzeContour", files={"file": ("decoy.kml", kml)})
    assert accepted.status_code == 202
    job_id = accepted.json()["job_id"]
    status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert status["status"] == "failed"
    assert status["error"]["code"] == "elevation_not_found"
    assert client.get(f"/api/v1/jobs/{job_id}/result").status_code == 409


def test_cancel_is_idempotent(client: TestClient) -> None:
    kml = (
        b"<kml><Document><Placemark><name>10</name><LineString><coordinates>"
        b"81,21 81.001,21</coordinates></LineString></Placemark></Document></kml>"
    )
    job_id = client.post("/api/v1/analyzeContour", files={"file": ("t.kml", kml)}).json()["job_id"]
    assert client.delete(f"/api/v1/jobs/{job_id}").status_code == 204
    assert client.delete(f"/api/v1/jobs/{job_id}").status_code == 204
    assert client.delete("/api/v1/jobs/3f2a9c1e-5b7d-4e8a-9c1f-2d6b8e4a7c93").status_code == 404
