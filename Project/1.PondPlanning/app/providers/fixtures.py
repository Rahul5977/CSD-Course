"""Fixture provider — the P0 stand-in for every engine that is not built yet.

Why this exists
---------------
The API contract is defined in full before any engine is written, so the
frontend can be built against realistic payloads from day one instead of waiting
for P3 or P4. That parallelism is the whole point of P0; skipping it serialises
the project.

Why the fixtures are honest about being fixtures
------------------------------------------------
A stub that is indistinguishable from a real result is a trap — for the frontend,
which starts depending on numbers that will change, and for an evaluator, who
cannot tell what is implemented. Every fixture payload therefore carries a
``fixture_data`` warning at ``critical`` severity, and every fixture route sets
the ``X-Fixture-Data: true`` response header. When an engine lands, its route
stops calling this provider and both signals disappear on their own.

The fixture village is deliberately **not** the sample contour map's area of
interest. Nothing in this package may become a source of truth for the sample.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from app.domain.errors import NotFoundError

FIXTURE_DIR = Path(__file__).parent / "fixture_data"

#: Set on every response served from this provider.
FIXTURE_HEADER = "X-Fixture-Data"


@cache
def _load(name: str) -> str:
    """Read one fixture file, cached as text so each caller gets a fresh object."""
    path = FIXTURE_DIR / f"{name}.json"
    if not path.is_file():
        msg = f"no fixture named {name!r}"
        raise NotFoundError(msg, {"available": sorted(p.stem for p in FIXTURE_DIR.glob("*.json"))})
    return path.read_text(encoding="utf-8")


def load(name: str) -> Any:
    """Return the named fixture payload.

    Args:
        name: Fixture file stem, e.g. ``"pond_design"``.

    Returns:
        The parsed JSON. A new object each call, so a route that mutates its
        response cannot corrupt another request's data.

    Raises:
        NotFoundError: If no such fixture exists.
    """
    return json.loads(_load(name))


def load_keyed(name: str, key: str) -> Any:
    """Return one entry from a fixture file that holds a mapping of variants.

    Used by the derived-surface routes, where slope, aspect, curvature, TWI,
    hillshade and flow accumulation share one file and one response shape.

    Raises:
        NotFoundError: If the fixture or the key is absent.
    """
    payload = load(name)
    if key not in payload:
        msg = f"{key!r} is not available"
        raise NotFoundError(msg, {"available": sorted(payload)})
    return payload[key]


def available() -> list[str]:
    """List every fixture stem. Used by the contract self-test."""
    return sorted(p.stem for p in FIXTURE_DIR.glob("*.json"))
