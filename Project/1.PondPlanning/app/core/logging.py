"""Structured logging.

Written against the standard library rather than structlog/loguru: the whole
implementation is forty legible lines, which is easier to justify in a live
demonstration than a dependency whose configuration nobody can explain.

Two formats. ``console`` for a human at a terminal, ``json`` for the Docker
deployment, where one object per line is what a log shipper can actually parse
and what the Grafana/Loki dashboard in P6 queries.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

# Attributes present on every LogRecord. Anything *not* in this set was passed
# by the caller via `extra=` and is therefore structured context worth emitting.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Render each record as a single-line JSON object, with the correlation id."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialise ``record``, merging any ``extra=`` keys into the payload."""
        from app.core.observability import request_id_var

        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _RESERVED})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", fmt: str = "console") -> None:
    """Install a single stdout handler on the root logger.

    Idempotent: repeated calls replace the handler rather than stacking, so
    reloads under ``uvicorn --reload`` do not duplicate every line.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if fmt == "json"
        else logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s", "%H:%M:%S")
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn installs its own handlers; make them propagate to ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
