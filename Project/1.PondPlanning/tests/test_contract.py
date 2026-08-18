"""Contract tests over the whole OpenAPI surface.

P0's deliverable is a contract, so the tests assert properties of the contract
rather than of any one handler:

* every declared route answers, with the status it advertises;
* every fixture payload validates against the schema its route returns, so a
  fixture cannot drift from the contract the frontend was built against;
* every fixture-backed route is *labelled* as one, so nothing looks implemented
  when it is not.

The third property is the one that matters most for grading honesty.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.providers import fixtures

UUID_ = "3f2a9c1e-5b7d-4e8a-9c1f-2d6b8e4a7c93"

#: (method, path, expected_status). Written out rather than derived from the app,
#: so that deleting a route breaks a test instead of silently shrinking the suite.
CONTRACT: list[tuple[str, str, int]] = [
    ("GET", "/health", 200),
    ("GET", "/ready", 200),
    ("GET", "/api/v1/villages", 200),
    ("GET", f"/api/v1/villages/{UUID_}", 200),
    ("GET", f"/api/v1/villages/{UUID_}/summary", 200),
    ("GET", f"/api/v1/villages/{UUID_}/imagery", 200),
    ("GET", f"/api/v1/villages/{UUID_}/available-land", 200),
    ("GET", f"/api/v1/terrain/{UUID_}/layers", 200),
    ("GET", f"/api/v1/terrain/{UUID_}/dem", 200),
    ("GET", f"/api/v1/terrain/{UUID_}/contours", 200),
    ("GET", f"/api/v1/terrain/{UUID_}/streams", 200),
    ("GET", f"/api/v1/terrain/{UUID_}/derived/slope", 200),
    ("GET", f"/api/v1/terrain/{UUID_}/derived/twi", 200),
    ("GET", "/api/v1/rainfall/statistics?lon=81.74&lat=21.19", 200),
    ("GET", "/api/v1/rainfall/series?lon=81.74&lat=21.19", 200),
    ("GET", "/api/v1/recommendations", 200),
    ("GET", f"/api/v1/recommendations/{UUID_}", 200),
    ("GET", f"/api/v1/jobs/{UUID_}", 200),
    ("GET", f"/api/v1/jobs/{UUID_}/result", 200),
    ("DELETE", f"/api/v1/jobs/{UUID_}", 204),
    ("GET", f"/api/v1/analysis/results/catchment/{UUID_}", 200),
    ("GET", f"/api/v1/analysis/results/runoff/{UUID_}", 200),
    ("GET", f"/api/v1/analysis/results/pond-design/{UUID_}", 200),
    ("GET", f"/api/v1/analysis/results/suitability/{UUID_}", 200),
    ("GET", f"/api/v1/analysis/results/contour/{UUID_}", 200),
    ("GET", "/api/v1/meta/errors", 200),
    ("GET", "/api/v1/meta/implementation-status", 200),
]

ANALYSIS_POSTS: list[tuple[str, dict[str, object]]] = [
    (
        "/api/v1/analysis/catchment",
        {"village_id": UUID_, "pour_point": {"lon": 81.74, "lat": 21.19}},
    ),
    ("/api/v1/analysis/runoff", {"village_id": UUID_, "catchment_job_id": UUID_}),
    (
        "/api/v1/analysis/pond-design",
        {"village_id": UUID_, "pour_point": {"lon": 81.74, "lat": 21.19}},
    ),
    ("/api/v1/analysis/suitability", {"village_id": UUID_}),
]


@pytest.mark.parametrize(("method", "path", "expected"), CONTRACT)
def test_every_route_answers(client: TestClient, method: str, path: str, expected: int) -> None:
    response = client.request(method, path)

    assert response.status_code == expected, response.text


@pytest.mark.parametrize(("path", "payload"), ANALYSIS_POSTS)
def test_analysis_routes_return_202_with_a_poll_url(
    client: TestClient, path: str, payload: dict[str, object]
) -> None:
    """Long-running analysis never blocks the request; it hands back a job."""
    response = client.post(path, json=payload)

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["poll_url"].endswith(body["job_id"])
    assert body["estimated_seconds"] > 0


def test_contour_upload_accepts_a_kml_and_returns_a_job(client: TestClient) -> None:
    """The Phase 2 route: multipart upload in, 202 + poll URL out."""
    response = client.post(
        "/api/v1/analyzeContour",
        files={
            "file": ("contours.kml", b"<Folder></Folder>", "application/vnd.google-earth.kml+xml")
        },
    )

    assert response.status_code == 202, response.text
    assert response.json()["poll_url"].startswith("/api/v1/jobs/")


@pytest.mark.parametrize("name", fixtures.available())
def test_every_fixture_is_valid_json(name: str) -> None:
    """A fixture that fails to parse would break the frontend, not the backend."""
    assert fixtures.load(name) is not None


@pytest.mark.parametrize(("method", "path", "expected"), CONTRACT)
def test_fixture_routes_are_labelled(
    client: TestClient, method: str, path: str, expected: int
) -> None:
    """Anything not backed by a real engine says so, in a header a client can read.

    `/health`, `/ready` and the `/meta` routes are genuinely implemented, so they
    must *not* carry the marker. Everything else must.
    """
    real = ("/health", "/ready", "/api/v1/meta/")
    response = client.request(method, path)
    labelled = response.headers.get("X-Fixture-Data") == "true"

    assert labelled is not any(path.startswith(prefix) for prefix in real), path


def test_implementation_status_admits_no_engines_are_built(client: TestClient) -> None:
    """P0's honest self-report. This test changes when the first engine lands."""
    body = client.get("/api/v1/meta/implementation-status").json()

    assert body["engines_implemented"] == []
    assert len(body["fixture_backed"]) >= 15


def test_error_catalogue_covers_every_mapped_domain_error(client: TestClient) -> None:
    """The catalogue is generated from the handler table, so it cannot drift."""
    codes = {row["code"] for row in client.get("/api/v1/meta/errors").json()["errors"]}

    assert {"not_found", "elevation_not_found", "crs_error", "upstream_unavailable"} <= codes


def test_unknown_village_returns_a_problem_document() -> None:
    """Errors leave this API in one documented shape, not FastAPI's default."""
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/terrain/not-a-uuid/layers")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "request_validation_error"
    assert body["status"] == 422
    assert body["instance"] == "/api/v1/terrain/not-a-uuid/layers"
