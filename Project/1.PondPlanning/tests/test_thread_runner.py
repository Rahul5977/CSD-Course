"""ThreadJobRunner: the one-process deployment's worker (lab VMs).

The POST must return before the job finishes (the async contract), jobs still
reach a terminal state, and a full bulkhead answers 429 instead of queueing
without bound.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.jobs.context import get_context
from app.jobs.runner import ThreadJobRunner
from app.main import create_app
from tests.conftest import SAMPLE_KML

pytestmark = pytest.mark.skipif(not SAMPLE_KML.exists(), reason="sample map not present")


@pytest.fixture
def threaded(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("POND_JOB_RUNNER", "thread")
    get_settings.cache_clear()
    get_context.cache_clear()
    from app.api.deps import reset_dependency_caches

    reset_dependency_caches()
    return TestClient(create_app())


def _upload(client: TestClient) -> tuple[int, dict]:  # type: ignore[type-arg]
    with SAMPLE_KML.open("rb") as handle:
        r = client.post(
            "/api/v1/analyzeContour",
            files={
                "contour_map": (SAMPLE_KML.name, handle, "application/vnd.google-earth.kml+xml")
            },
        )
    return r.status_code, r.json()


def test_post_returns_before_the_job_finishes_and_the_job_completes(threaded: TestClient) -> None:
    started = time.perf_counter()
    status, body = _upload(threaded)
    assert status == 202
    assert time.perf_counter() - started < 1.5, "202 comes back immediately"
    first = threaded.get(f"/api/v1/jobs/{body['job_id']}").json()["status"]
    assert first in {"queued", "running", "succeeded"}
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        job = threaded.get(f"/api/v1/jobs/{body['job_id']}").json()
        if job["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.2)
    assert job["status"] == "succeeded", job


def test_a_full_bulkhead_answers_429(threaded: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(ThreadJobRunner._pending, "heavy", 10_000)
    status, body = _upload(threaded)
    assert status == 429 and body["code"] == "queue_saturated"
