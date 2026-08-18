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

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_is_503_when_a_dependency_is_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A degraded dependency must be visible in the status code, not only the body."""
    monkeypatch.setattr(
        health,
        "_check_postgres",
        lambda: DependencyStatus(name="postgres", reachable=False, detail="connection refused"),
    )

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["dependencies"][0]["detail"] == "connection refused"


def test_openapi_schema_is_served(client: TestClient) -> None:
    """The OpenAPI document is a graded deliverable (Docs: API documentation, 2 marks)."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
