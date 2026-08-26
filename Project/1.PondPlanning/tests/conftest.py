"""Shared fixtures.

The suite runs with the in-memory, inline and local-filesystem adapters, so it
needs neither Docker nor a network. The environment is set *before* the app is
imported, because settings are read once at import time.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

_STORE_DIR = Path(tempfile.mkdtemp(prefix="pond-store-"))
os.environ.update(
    {
        "POND_ENV": os.environ.get("POND_ENV", "ci"),
        "POND_PERSISTENCE": "memory",
        "POND_JOB_RUNNER": "inline",
        "POND_OBJECT_STORE": "local",
        "POND_LOCAL_STORE_DIR": str(_STORE_DIR),
        "POND_GEOCODE_ENABLED": "false",
        "POND_RAINFALL_SOURCE": "recorded",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import reset_dependency_caches  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.jobs.context import get_context  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories import reset_memory_repositories  # noqa: E402

SAMPLE_KML = Path(__file__).resolve().parents[1] / "data" / "samples" / "contours_1m.kml"


@pytest.fixture(autouse=True)
def _fresh_state() -> Iterator[None]:
    """Every test starts with empty repositories and freshly built adapters."""
    get_settings.cache_clear()
    reset_memory_repositories()
    reset_dependency_caches()
    get_context.cache_clear()
    yield


@pytest.fixture
def client() -> TestClient:
    """A TestClient over a freshly built app."""
    return TestClient(create_app())
