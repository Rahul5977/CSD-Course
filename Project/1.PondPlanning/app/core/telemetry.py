"""OpenTelemetry: traces, metrics and logs over OTLP (ADR 0022).

**What is emitted.**

* *Traces* — every HTTP request (FastAPI instrumentation), every SQL statement
  (SQLAlchemy), every Redis command and Celery publish/run (so one trace
  crosses the broker from the API into the worker), every outbound provider
  call (urllib: Open-Meteo, WorldCover, SoilGrids, Nominatim), plus one span
  per analysis job and **one child span per pipeline stage** — Priority-Flood,
  D8, siting, catchment — so a trace waterfall reads as the algorithm.
* *Metrics* — the instrumentations' standard HTTP/DB metrics plus the domain
  instruments below (job and stage durations, catchment area, pond storage).
* *Logs* — every stdlib log record is exported over OTLP with the trace and
  span id of the code that wrote it; the JSON stdout formatter adds the same
  ids, so a log line and its trace are one click apart.

**How the stage spans stay out of the engines.** The workflows already record
their progress with ``jobs.update(stage=...)``. :class:`StageObservingJobs`
decorates the job repository (Decorator pattern) and turns each stage change
into a span: the engines and workflows never import OpenTelemetry and keep
their layering (``tests/test_layering.py``).

Everything is off unless ``POND_OTEL_ENABLED=true``; with it off the API's
no-op providers make every call here free, so tests and the lab VMs need no
collector.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from opentelemetry import context as otel_context
from opentelemetry import metrics, trace
from opentelemetry.trace import Span, Status, StatusCode

from app import __version__
from app.core.config import Settings

logger = logging.getLogger(__name__)

tracer = trace.get_tracer("pond.jobs", __version__)
meter = metrics.get_meter("pond.jobs", __version__)

# Domain instruments. Created against the global proxy, so they are no-ops
# until setup_telemetry() installs a real MeterProvider, and live after it.
JOB_DURATION = meter.create_histogram(
    "pond.job.duration", unit="s", description="Analysis job wall time, by kind and outcome"
)
STAGE_DURATION = meter.create_histogram(
    "pond.job.stage.duration", unit="s", description="Wall time of one pipeline stage"
)
JOBS_ACTIVE = meter.create_up_down_counter(
    "pond.jobs.active", unit="{job}", description="Jobs currently executing, by kind"
)
CATCHMENT_AREA = meter.create_histogram(
    "pond.catchment.area", unit="ha", description="Delineated catchment area per result"
)
POND_STORAGE = meter.create_histogram(
    "pond.design.storage", unit="m3", description="Designed gross storage per pond design"
)


@dataclass(frozen=True, slots=True)
class TelemetryHandles:
    """The installed providers, kept so tests can flush and shut them down."""

    tracer_provider: Any
    meter_provider: Any
    logger_provider: Any

    def shutdown(self) -> None:
        """Flush every pending batch (spans, metrics, logs) and stop the exporters."""
        for provider in (self.tracer_provider, self.meter_provider, self.logger_provider):
            provider.shutdown()


_installed: TelemetryHandles | None = None


def setup_telemetry(
    settings: Settings,
    service_name: str | None = None,
    *,
    span_exporter: Any = None,
    metric_reader: Any = None,
    log_exporter: Any = None,
) -> TelemetryHandles | None:
    """Install the three SDK providers and the library instrumentations, once per process.

    The exporters default to OTLP/HTTP at ``settings.otel_endpoint`` (the
    collector); tests pass in-memory ones. Returns ``None`` when disabled.
    """
    global _installed
    if _installed is not None:
        return _installed
    if not settings.otel_enabled and span_exporter is None:
        return None

    from opentelemetry._logs import set_logger_provider
    from opentelemetry.instrumentation.logging.handler import LoggingHandler
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # The Resource says *who* is talking: every span, metric point and log
    # record carries these attributes, which is how Jaeger separates the API
    # from each worker and Grafana filters by deployment.
    resource = Resource.create(
        {
            "service.name": service_name or settings.otel_service_name,
            "service.namespace": "pond-planner",
            "service.version": __version__,
            "deployment.environment": settings.env,
        }
    )
    endpoint = settings.otel_endpoint.rstrip("/")

    if span_exporter is None:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        span_exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
    tracer_provider = TracerProvider(resource=resource)
    # Batching: spans are queued and sent every few seconds on a background
    # thread, so a request never waits on the collector.
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    if metric_reader is None:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
            export_interval_millis=int(settings.otel_metric_interval_s * 1000),
        )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    if log_exporter is None:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

        log_exporter = OTLPLogExporter(endpoint=f"{endpoint}/v1/logs")
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(logger_provider)
    handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    # The exporters log their own failures; exporting those would loop.
    handler.addFilter(lambda record: not record.name.startswith("opentelemetry"))
    attach_log_handler(handler)

    _instrument_libraries(settings)
    _installed = TelemetryHandles(tracer_provider, meter_provider, logger_provider)
    logger.info(
        "opentelemetry enabled",
        extra={"otel_service": resource.attributes["service.name"], "otel_endpoint": endpoint},
    )
    return _installed


_log_handler: logging.Handler | None = None


def attach_log_handler(handler: logging.Handler | None = None) -> None:
    """Put the OTLP log handler on the root logger (again, after a framework resets it).

    ``configure_logging`` and Celery's worker both replace the root handlers;
    each calls this afterwards so the OTLP export survives.
    """
    global _log_handler
    if handler is not None:
        _log_handler = handler
    root = logging.getLogger()
    if _log_handler is not None and _log_handler not in root.handlers:
        root.addHandler(_log_handler)


def _instrument_libraries(settings: Settings) -> None:
    """Auto-instrumentation: patch the libraries the app already uses."""
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.urllib import URLLibInstrumentor

    CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]
    RedisInstrumentor().instrument()
    URLLibInstrumentor().instrument()
    if settings.persistence == "postgres":
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        from app.core.db import engine

        SQLAlchemyInstrumentor().instrument(engine=engine)


def instrument_app(app: Any) -> None:
    """Server spans + HTTP metrics for every route; probes and scrapes are skipped."""
    if _installed is None:
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    # ASGI "receive"/"send" spans are one per body chunk: a 6 MB upload made ~85
    # of them and buried the pipeline in the waterfall.
    FastAPIInstrumentor.instrument_app(
        app, excluded_urls="health,ready,metrics", exclude_spans=["receive", "send"]
    )


def current_trace_ids() -> tuple[str, str] | None:
    """``(trace_id, span_id)`` of the active span as hex, or ``None`` outside a trace."""
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


# -- job and stage spans ------------------------------------------------------


class _StageSpans:
    """Turns a sequence of stage names into consecutive child spans of the job span.

    Each new stage ends the previous span and starts the next, and makes it
    *current*, so the SQL, Redis and HTTP spans emitted during the stage nest
    under it. Attach/detach happen on the job's own thread in LIFO order.
    """

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._span: Span | None = None
        self._token: object | None = None
        self._name = ""
        self._started = 0.0

    def enter(self, stage: str) -> None:
        if stage == self._name:
            return
        self.close()
        self._name = stage
        self._started = time.perf_counter()
        self._span = tracer.start_span(
            f"stage: {stage}", attributes={"pond.job.kind": self.kind, "pond.stage": stage}
        )
        self._token = otel_context.attach(trace.set_span_in_context(self._span))

    def close(self, error: str | None = None) -> None:
        if self._span is None:
            return
        if error:
            self._span.set_status(Status(StatusCode.ERROR, error))
        if self._token is not None:
            otel_context.detach(self._token)  # type: ignore[arg-type]
        self._span.end()
        STAGE_DURATION.record(
            time.perf_counter() - self._started,
            {"pond.job.kind": self.kind, "pond.stage": self._name},
        )
        self._span, self._token, self._name = None, None, ""


_stage_spans: ContextVar[_StageSpans | None] = ContextVar("pond_stage_spans", default=None)

_TERMINAL = frozenset({"done", "failed", "compensated"})


@contextmanager
def job_span(kind: str, job_id: str) -> Iterator[Span]:
    """One span around a whole analysis job, with its stages as children."""
    stages = _StageSpans(kind)
    token = _stage_spans.set(stages)
    JOBS_ACTIVE.add(1, {"pond.job.kind": kind})
    started = time.perf_counter()
    outcome = "succeeded"
    with tracer.start_as_current_span(
        f"job {kind}", attributes={"pond.job.kind": kind, "pond.job.id": job_id}
    ) as span:
        try:
            yield span
        except Exception as exc:
            outcome = "failed"
            stages.close(error=type(exc).__name__)
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)[:200]))
            raise
        finally:
            stages.close()
            span.set_attribute("pond.job.outcome", outcome)
            JOBS_ACTIVE.add(-1, {"pond.job.kind": kind})
            JOB_DURATION.record(
                time.perf_counter() - started, {"pond.job.kind": kind, "pond.job.outcome": outcome}
            )
            _stage_spans.reset(token)


def _quantity(result: Any, *path: str) -> float | None:
    node = result
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    value = node.get("value") if isinstance(node, dict) else None
    return float(value) if isinstance(value, int | float) else None


def record_result(result: Any) -> None:
    """Domain metrics + span attributes from a finished job's result payload."""
    span = trace.get_current_span()
    area = _quantity(result, "area") or _quantity(result, "catchment", "area")
    if area is not None:
        CATCHMENT_AREA.record(area)
        span.set_attribute("pond.catchment.area_ha", area)
    storage = _quantity(result, "gross_storage")
    if storage is not None:
        POND_STORAGE.record(storage)
        span.set_attribute("pond.design.gross_storage_m3", storage)


class StageObservingJobs:
    """Decorator over a ``JobRepository``: stage changes become spans.

    Delegates every call unchanged; on ``update`` it reads the ``stage`` and
    ``status`` fields the workflows already write and drives the stage spans
    of the job currently running in this context. Outside a job (the API
    creating a row) there is no active job span and it does nothing extra.
    """

    def __init__(self, inner: Any) -> None:
        """Wrap ``inner``, the real repository."""
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        """Delegate everything but ``update`` untouched."""
        return getattr(self._inner, name)

    def update(self, job_id: UUID, **fields: Any) -> Any:
        """Drive the stage spans from ``stage``/``status``, then write through."""
        stages = _stage_spans.get()
        stage = fields.get("stage")
        if stages is not None and isinstance(stage, str):
            if stage in _TERMINAL:
                error = str(fields.get("error") or stage) if stage != "done" else None
                stages.close(error=error)
                if fields.get("status") == "succeeded":
                    record_result(fields.get("result"))
                elif error:
                    trace.get_current_span().set_status(Status(StatusCode.ERROR, error[:200]))
            else:
                stages.enter(stage)
        return self._inner.update(job_id, **fields)
