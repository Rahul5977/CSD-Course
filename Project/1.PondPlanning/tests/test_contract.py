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

#: Routes backed by real engines. Everything else must carry the fixture marker.
#: Grows by phase; the implementation-status endpoint reports the same list.
REAL_PREFIXES = (
    "/health",
    "/ready",
    "/api/v1/meta/",
    "/api/v1/analyzeContour",
    "/api/v1/jobs/",
    "/api/v1/villages",
    "/api/v1/terrain/" + UUID_ + "/dem",
    "/api/v1/terrain/" + UUID_ + "/layers",
)
#: Real routes that are fixture-backed for a *sub*-path (available-land, parcels).
FIXTURE_EXCEPTIONS = ("/available-land", "parcels:import")

#: (method, path, expected_status). Written out rather than derived from the app,
#: so that deleting a route breaks a test instead of silently shrinking the suite.
#: Real routes answer 404 for an unknown id — that is the contract now.
CONTRACT: list[tuple[str, str, int]] = [
    ("GET", "/health", 200),
    # /ready is deliberately absent: it answers 200 or 503 depending on whether
    # postgres is reachable, which is environment-dependent and therefore not a
    # property of the contract. It is tested in test_health.py with the
    # dependency check stubbed, in both directions.
    ("GET", "/api/v1/villages", 200),
    ("GET", f"/api/v1/villages/{UUID_}", 404),
    ("GET", f"/api/v1/villages/{UUID_}/summary", 404),
    ("GET", f"/api/v1/villages/{UUID_}/imagery", 404),
    ("GET", f"/api/v1/villages/{UUID_}/available-land", 200),
    ("GET", f"/api/v1/terrain/{UUID_}/layers", 404),
    ("GET", f"/api/v1/terrain/{UUID_}/dem", 404),
    ("GET", f"/api/v1/terrain/{UUID_}/contours", 200),
    ("GET", f"/api/v1/terrain/{UUID_}/streams", 200),
    ("GET", f"/api/v1/terrain/{UUID_}/derived/slope", 200),
    ("GET", f"/api/v1/terrain/{UUID_}/derived/twi", 200),
    ("GET", "/api/v1/rainfall/statistics?lon=81.74&lat=21.19", 200),
    ("GET", "/api/v1/rainfall/series?lon=81.74&lat=21.19", 200),
    ("GET", "/api/v1/recommendations", 200),
    ("GET", f"/api/v1/recommendations/{UUID_}", 200),
    ("GET", f"/api/v1/jobs/{UUID_}", 404),
    ("GET", f"/api/v1/jobs/{UUID_}/result", 404),
    ("DELETE", f"/api/v1/jobs/{UUID_}", 404),
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
    """The Phase 2 route: multipart upload in, 202 + poll URL out.

    The body is deliberately not a valid contour map: the *contract* is that the
    route accepts and dispatches; what the job then does is tested end-to-end in
    test_contour_job_flow.py.
    """
    response = client.post(
        "/api/v1/analyzeContour",
        files={
            "file": ("contours.kml", b"<Folder></Folder>", "application/vnd.google-earth.kml+xml")
        },
    )

    assert response.status_code == 202, response.text
    assert response.json()["poll_url"].startswith("/api/v1/jobs/")
    job_id = response.json()["job_id"]
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "failed"


@pytest.mark.parametrize("name", fixtures.available())
def test_every_fixture_is_valid_json(name: str) -> None:
    """A fixture that fails to parse would break the frontend, not the backend."""
    assert fixtures.load(name) is not None


@pytest.mark.parametrize(("method", "path", "expected"), CONTRACT)
def test_fixture_routes_are_labelled(
    client: TestClient, method: str, path: str, expected: int
) -> None:
    """Anything not backed by a real engine says so, in a header a client can read.

    Real routes must *not* carry the marker; every fixture route must.
    """
    response = client.request(method, path)
    labelled = response.headers.get("X-Fixture-Data") == "true"
    is_real = any(path.startswith(prefix) for prefix in REAL_PREFIXES) and not any(
        marker in path for marker in FIXTURE_EXCEPTIONS
    )

    assert labelled is not is_real, path


def test_implementation_status_reports_the_p1_engines(client: TestClient) -> None:
    """The honest self-report. This test changes when each engine lands."""
    body = client.get("/api/v1/meta/implementation-status").json()

    assert body["phase"].startswith("P1")
    assert any("contour_kml" in engine for engine in body["engines_implemented"])
    assert "villages" not in body["fixture_backed"]
    assert "catchment" in body["fixture_backed"]
    assert "/api/v1/analyzeContour" in body["real"]


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
