"""The contour pipeline's persistence saga compensates on an injected failure."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_repositories
from app.providers.raster_io import write_cog
from tests.conftest import SAMPLE_KML

pytestmark = pytest.mark.skipif(not SAMPLE_KML.exists(), reason="sample map not present")


def test_failure_after_village_creation_rolls_the_village_back(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = set(_stored_keys())
    calls = {"n": 0}
    real = write_cog

    def flaky_write_cog(*args: object, **kwargs: object) -> bytes:
        calls["n"] += 1
        if calls["n"] == 3:
            msg = "object store went away"
            raise OSError(msg)
        return bytes(real(*args, **kwargs))  # type: ignore[arg-type]

    monkeypatch.setattr("app.engines.workflows.contour_analysis.write_cog", flaky_write_cog)
    with SAMPLE_KML.open("rb") as handle:
        job_id = client.post(
            "/api/v1/analyzeContour", files={"contour_map": (SAMPLE_KML.name, handle)}
        ).json()["job_id"]
    status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert status["status"] == "failed"
    repos = get_repositories()
    job = repos.jobs.get(__import__("uuid").UUID(job_id))
    assert job is not None and job.result is not None
    assert job.result["code"] in {"persistence_failed", "internal_error"}
    if job.result["code"] == "persistence_failed":
        assert job.result["detail"]["failed_step"] == "rasters"
        assert job.result["detail"]["compensated"] == ["village"]
    assert client.get("/api/v1/villages").json()["total"] == 0, (
        "the half-registered village was removed"
    )
    new_keys = set(_stored_keys()) - before
    assert not any(k.startswith("villages/") for k in new_keys), new_keys
    assert any(k.startswith("uploads/") for k in new_keys), "the upload itself is kept for retry"


def _stored_keys() -> list[str]:
    from pathlib import Path

    from app.core.config import get_settings

    root = Path(get_settings().local_store_dir)
    return [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
