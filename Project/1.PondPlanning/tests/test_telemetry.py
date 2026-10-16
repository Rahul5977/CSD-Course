"""OpenTelemetry (ADR 0022): what is emitted, and that it joins up into one trace.

The SDK is installed once for this process with in-memory exporters, so the
assertions read exactly what the collector would have received.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core.config import get_settings
from app.core.logging import JsonFormatter
from app.core.telemetry import StageObservingJobs, TelemetryHandles, job_span, setup_telemetry
from app.main import create_app
from app.repositories.memory import InMemoryJobRepository
from tests.conftest import SAMPLE_KML

SPANS = InMemorySpanExporter()
METRICS = InMemoryMetricReader()
LOGS = InMemoryLogRecordExporter()  # type: ignore[no-untyped-call]


@pytest.fixture(scope="module")
def otel() -> TelemetryHandles:
    """Install the SDK once (OpenTelemetry's global providers can be set only once)."""
    handles = setup_telemetry(
        get_settings(), "pond-test", span_exporter=SPANS, metric_reader=METRICS, log_exporter=LOGS
    )
    assert handles is not None
    return handles


@pytest.fixture
def spans(otel: TelemetryHandles) -> Iterator[Any]:
    """Finished spans of this test only, flushed on read."""
    SPANS.clear()

    def finished() -> list[Any]:
        otel.tracer_provider.force_flush()
        return list(SPANS.get_finished_spans())

    yield finished


def _metric_names() -> set[str]:
    data = METRICS.get_metrics_data()
    return {
        metric.name
        for resource in (data.resource_metrics if data else [])
        for scope in resource.scope_metrics
        for metric in scope.metrics
    }


def test_each_stage_becomes_a_child_span_of_the_job(spans: Any) -> None:
    repo = InMemoryJobRepository()
    job = repo.create(kind="catchment", params={}, village_id=None)
    jobs = StageObservingJobs(repo)
    with job_span("catchment", str(job.id)):
        jobs.update(job.id, status="running", stage="snapping to drainage")
        jobs.update(job.id, status="running", stage="tracing upstream cells")
        jobs.update(
            job.id,
            status="succeeded",
            stage="done",
            result={"area": {"value": 38.25, "unit": "ha"}},
        )

    by_name = {s.name: s for s in spans()}
    root = by_name["job catchment"]
    snap = by_name["stage: snapping to drainage"]
    trace_ = by_name["stage: tracing upstream cells"]
    assert snap.parent.span_id == root.context.span_id
    assert trace_.parent.span_id == root.context.span_id
    assert snap.end_time <= trace_.start_time, "stages are consecutive, not nested"
    assert root.attributes["pond.catchment.area_ha"] == 38.25
    assert root.attributes["pond.job.outcome"] == "succeeded"
    stored = repo.get(job.id)
    assert stored is not None
    assert stored.stage == "done", "the decorator writes through unchanged"
    assert {"pond.job.duration", "pond.job.stage.duration", "pond.catchment.area"} <= (
        _metric_names()
    )


def test_a_failed_job_marks_its_stage_and_the_job_as_errors(spans: Any) -> None:
    repo = InMemoryJobRepository()
    job = repo.create(kind="runoff", params={}, village_id=None)
    jobs = StageObservingJobs(repo)
    with pytest.raises(RuntimeError), job_span("runoff", str(job.id)):
        jobs.update(job.id, status="running", stage="daily rainfall")
        raise RuntimeError("provider down")

    by_name = {s.name: s for s in spans()}
    assert not by_name["stage: daily rainfall"].status.is_ok
    root = by_name["job runoff"]
    assert not root.status.is_ok
    assert root.attributes["pond.job.outcome"] == "failed"
    assert any(event.name == "exception" for event in root.events)


def test_json_log_lines_carry_the_active_trace_id(otel: TelemetryHandles) -> None:
    record = logging.LogRecord("pond", logging.INFO, __file__, 1, "inside a span", None, None)
    with trace.get_tracer("t").start_as_current_span("s") as span:
        line = json.loads(JsonFormatter().format(record))
    assert line["trace_id"] == format(span.get_span_context().trace_id, "032x")
    assert "trace_id" not in json.loads(JsonFormatter().format(record)), "none outside a span"


def test_logs_are_exported_with_their_trace_context(otel: TelemetryHandles) -> None:
    LOGS.clear()
    with trace.get_tracer("t").start_as_current_span("s") as span:
        logging.getLogger("pond.test").warning("exported over otlp %s", uuid4())
    otel.logger_provider.force_flush()
    exported = [
        r for r in LOGS.get_finished_logs() if str(r.log_record.body).startswith("exported over")
    ]
    assert exported, "the root logger's OTLP handler exported the record"
    assert exported[0].log_record.trace_id == span.get_span_context().trace_id


@pytest.mark.skipif(not SAMPLE_KML.exists(), reason="sample map not present")
def test_one_upload_is_one_trace_from_http_to_priority_flood(spans: Any) -> None:
    """The viva screenshot as a test: request span → job span → algorithm stages."""
    client = TestClient(create_app())
    with SAMPLE_KML.open("rb") as handle:
        response = client.post(
            "/api/v1/analyzeContour",
            files={"contour_map": (SAMPLE_KML.name, handle, "application/xml")},
        )
    assert response.status_code == 202, response.text

    finished = spans()
    by_name = {s.name: s for s in finished}
    request = by_name["POST /api/v1/analyzeContour"]
    job = by_name["job contour_analysis"]
    stages = [s for s in finished if s.name.startswith("stage: ")]
    names = {s.name for s in stages}
    assert {
        "stage: filling sinks (Priority-Flood)",
        "stage: routing flow (D8) and accumulating",
        "stage: ranking pond sites",
        "stage: delineating the catchment of the top site",
    } <= names
    trace_id = request.context.trace_id
    assert job.context.trace_id == trace_id
    assert all(s.context.trace_id == trace_id for s in stages), "one trace end to end"
    assert job.attributes["pond.catchment.area_ha"] > 0
