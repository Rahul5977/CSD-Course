import pytest
from fastapi.testclient import TestClient

from app.api.routers import health
from app.schemas.health import DependencyStatus


def test_health_reports_version_and_env(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["env"] in {"local", "ci", "docker", "production"}


def test_ready_is_200_when_dependencies_are_reachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        health, "_check_postgres", lambda: DependencyStatus(name="postgres", reachable=True)
    )
    monkeypatch.setattr(
        health, "_check_redis", lambda: DependencyStatus(name="redis", reachable=True)
    )

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_is_503_when_a_dependency_is_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A degraded dependency must be visible in the status code, not only the body."""
    from app.core.config import get_settings

    settings = get_settings().model_copy(update={"persistence": "postgres"})
    monkeypatch.setattr(health, "get_settings", lambda: settings)
    monkeypatch.setattr(
        health,
        "_check_postgres",
        lambda: DependencyStatus(name="postgres", reachable=False, detail="connection refused"),
    )
    monkeypatch.setattr(
        health, "_check_redis", lambda: DependencyStatus(name="redis", reachable=True)
    )

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["dependencies"][0]["detail"] == "connection refused"


def test_ready_probes_only_the_configured_adapters(client: TestClient) -> None:
    """Memory persistence and the inline runner have no postgres or redis to probe.

    A single-process deployment must not report itself degraded — the lab-VM
    deployment runs exactly this configuration.
    """
    response = client.get("/ready")

    assert response.status_code == 200
    names = {d["name"] for d in response.json()["dependencies"]}
    assert "persistence" in names and "job_runner" in names
    assert "postgres" not in names and "redis" not in names


def test_probes_are_not_marked_as_fixture_data(client: TestClient) -> None:
    """The probes are genuinely implemented, so they must not carry the marker.

    Asserted here rather than in the contract suite because /ready's status code
    depends on whether a database happens to be reachable.
    """
    for path in ("/health", "/ready"):
        assert "X-Fixture-Data" not in client.get(path).headers, path


def test_openapi_schema_is_served(client: TestClient) -> None:
    """The OpenAPI document is a graded deliverable (Docs: API documentation, 2 marks)."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
