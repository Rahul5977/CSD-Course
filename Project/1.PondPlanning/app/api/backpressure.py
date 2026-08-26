"""Backpressure: refuse new analysis jobs when a queue is already deep (P6).

A queue deeper than ``max_queue_depth`` answers ``429 Too Many Requests`` with
``Retry-After``, so a burst degrades into a polite wait instead of a
minutes-long backlog nobody asked for. In-memory/inline mode has no queue and
never refuses.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.observability import RATE_LIMITED
from app.domain.errors import DomainError


class BackpressureError(DomainError):
    """The target queue is saturated; retry later."""

    code = "queue_saturated"

    def __init__(self, queue: str, depth: int, retry_after_s: int) -> None:
        """Carry the queue state for the problem document and the header."""
        super().__init__(
            f"the {queue} queue holds {depth} jobs; try again in {retry_after_s} s",
            {"queue": queue, "depth": depth, "retry_after_s": retry_after_s},
        )
        self.retry_after_s = retry_after_s


def accept_or_429(settings: Settings, queue: str) -> None:
    """Raise :class:`BackpressureError` when the queue is over the limit."""
    if settings.job_runner != "celery":
        return
    from app.providers.queues import queue_depth

    depth = queue_depth(settings.redis_url, queue)
    if depth >= settings.max_queue_depth:
        RATE_LIMITED.labels(queue).inc()
        raise BackpressureError(queue, depth, retry_after_s=max(5, depth * 3))
