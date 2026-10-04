"""Correlation ids and the metrics endpoint."""

from fastapi.testclient import TestClient


def test_every_response_carries_a_request_id_and_metrics_count_it(client: TestClient) -> None:
    given = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert given.headers["X-Request-ID"] == "trace-123"
    generated = client.get("/health")
    assert len(generated.headers["X-Request-ID"]) >= 12
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert 'pond_http_requests_total{method="GET",route="/health",status="200"}' in metrics.text
    assert "pond_http_request_seconds_bucket" in metrics.text
