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
    return client, result


def test_result_is_derived_from_the_upload(
    analysed: tuple[TestClient, dict],  # type: ignore[type-arg]
) -> None:
    _, result = analysed
    assert result["provider"] == "contour_kml"
    assert result["elevation_source"] == "placemark_name"
    assert result["contour_count"] == 1355
    assert result["contour_interval"]["value"] == 1.0
    assert result["utm_epsg"] == 32644, "zone derived from the file's own centroid"
    # A 30 m grid with sigma=1 smoothing cannot hold an isolated 1 m low/high, so the
    # extremes sit a metre or two inside the contour range — and that is honest,
    # given SRTM's ±6 m relative accuracy.
    assert result["elevation"]["minimum"]["value"] == pytest.approx(267.0, abs=2.5)
    assert result["elevation"]["maximum"]["value"] == pytest.approx(298.0, abs=2.5)
    assert result["grid_resolution"]["value"] >= 30.0, "floored at the SRTM source resolution"
    assert "SRTM" in result["dem"]["source"]
    assert result["dem"]["native_resolution"]["value"] == 30.0
    assert {layer["layer_id"] for layer in result["layers"]} >= {"satellite", "hillshade", "dem"}
    assert result["catchment"] is None
    assert result["elevation"]["minimum"]["display"].endswith("%)")  # unit + band


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
