"""Redis helpers for the job system: queue depth (backpressure, metrics) and a leader lock."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import redis

logger = logging.getLogger(__name__)


def queue_depth(redis_url: str, queue: str) -> int:
    """Length of a Celery queue list in Redis (0 if Redis is unreachable)."""
    try:
        client = redis.Redis.from_url(redis_url, socket_timeout=1.0)
        return int(client.llen(queue))  # type: ignore[arg-type]
    except redis.RedisError as exc:
        logger.warning("queue depth unavailable", extra={"queue": queue, "reason": str(exc)})
        return 0


@contextmanager
def leader_lock(redis_url: str, name: str, ttl_s: int) -> Iterator[bool]:
    """``SET NX EX`` lock: yields True for the one worker that won, False for the rest.

    The correct answer to "what if you run ten workers?" — a scheduled job runs
    once, on whichever worker acquires the key first; the TTL frees it if that
    worker dies mid-way.
    """
    client = redis.Redis.from_url(redis_url, socket_timeout=2.0)
    key = f"lock:{name}"
    token = "1"
    acquired = bool(client.set(key, token, nx=True, ex=ttl_s))
    try:
        yield acquired
    finally:
        if acquired:
            client.delete(key)
