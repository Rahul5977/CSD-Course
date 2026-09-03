"""FR6 through the API on the sample: catchment → runoff job → three-method range."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.engines.workflows import runoff as runoff_workflow
from app.providers.landcover import DefaultSoilAdapter, LandCoverWindow
from tests.conftest import SAMPLE_KML

pytestmark = pytest.mark.skipif(not SAMPLE_KML.exists(), reason="sample map not present")


class OfflineWorldCover:
    """A deterministic land-cover window so the test never touches AWS."""

    name = "offline"

    def window(self, bounds: tuple[float, float, float, float]) -> LandCoverWindow:
        """Random but seeded classes over the bounds."""
        w, s, e, n = bounds
        rng = np.random.default_rng(7)
        codes = rng.choice([40, 30, 10, 50], size=(60, 80), p=[0.5, 0.3, 0.1, 0.1]).astype(np.uint8)
        return LandCoverWindow(
            codes, ((e - w) / 80, 0.0, w, 0.0, -(n - s) / 60, n), "offline test land cover"
        )


def test_runoff_job_produces_a_three_method_range(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runoff_workflow, "WorldCoverAdapter", OfflineWorldCover)
    monkeypatch.setattr(runoff_workflow, "SoilGridsAdapter", lambda: DefaultSoilAdapter("C"))

    with SAMPLE_KML.open("rb") as handle:
        job = client.post(
            "/api/v1/analyzeContour", files={"contour_map": (SAMPLE_KML.name, handle)}
        ).json()["job_id"]
    contour = client.get(f"/api/v1/jobs/{job}/result").json()["result"]
    village_id = contour["village_id"]
    point = contour["suggested_pond_location"]
    catchment_job = client.post(
        "/api/v1/analysis/catchment", json={"village_id": village_id, "pour_point": point}
    ).json()["job_id"]

    accepted = client.post(
        "/api/v1/analysis/runoff",
        json={"village_id": village_id, "catchment_job_id": catchment_job, "years": 20},
    )
    assert accepted.status_code == 202, accepted.text
    runoff_job = accepted.json()["job_id"]
    status = client.get(f"/api/v1/jobs/{runoff_job}").json()
    assert status["status"] == "succeeded", status
    result = client.get(f"/api/v1/analysis/results/runoff/{runoff_job}").json()

    methods = {r["method"]: r for r in result["results"]}
    assert set(methods) == {"scs_cn", "rational", "empirical_strange"}
    assert result["recommended"]["method"] == "scs_cn"
    scs = methods["scs_cn"]
    assert (
        scs["annual_runoff_volume"]["unit"] == "m3"
        and scs["annual_runoff_volume"]["uncertainty_pct"] == 30
    )
    area_ha = result["catchment_area"]["value"]
    depth_mm = scs["parameters"]["dependable_75_runoff_depth"]["value"]
    assert scs["annual_runoff_volume"]["value"] == pytest.approx(
        depth_mm / 1000 * area_ha * 1e4, rel=1e-6
    )
    assert 50 < depth_mm < 900, "central India, CN ~80-88: a few hundred mm of runoff"
    assert 60 <= scs["parameters"]["curve_number"]["value"] <= 95
    assert 0 < result["spread_pct"]["value"] < 200
    assert any(w["code"] == "curve_number_basis" for w in result["warnings"])
    assert "X-Fixture-Data" not in accepted.headers


def test_runoff_for_a_missing_catchment_job_fails_honestly(client: TestClient) -> None:
    with SAMPLE_KML.open("rb") as handle:
        job = client.post(
            "/api/v1/analyzeContour", files={"contour_map": (SAMPLE_KML.name, handle)}
        ).json()["job_id"]
    village_id = client.get(f"/api/v1/jobs/{job}/result").json()["result"]["village_id"]
    runoff_job = client.post(
        "/api/v1/analysis/runoff",
        json={"village_id": village_id, "catchment_job_id": "3f2a9c1e-5b7d-4e8a-9c1f-2d6b8e4a7c93"},
    ).json()["job_id"]
    status = client.get(f"/api/v1/jobs/{runoff_job}").json()
    assert status["status"] == "failed" and status["error"]["code"] == "not_found"
