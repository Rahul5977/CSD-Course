"""FR7 through the API on the sample: pond design at the suggested site (offline providers)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.engines.workflows import runoff as runoff_workflow
from app.providers.landcover import DefaultSoilAdapter
from tests.conftest import SAMPLE_KML
from tests.test_runoff_flow import OfflineWorldCover

pytestmark = pytest.mark.skipif(not SAMPLE_KML.exists(), reason="sample map not present")


def test_pond_design_returns_the_full_payload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runoff_workflow, "WorldCoverAdapter", OfflineWorldCover)
    monkeypatch.setattr(runoff_workflow, "SoilGridsAdapter", lambda: DefaultSoilAdapter("C"))
    with SAMPLE_KML.open("rb") as handle:
        job = client.post(
            "/api/v1/analyzeContour", files={"file": (SAMPLE_KML.name, handle)}
        ).json()["job_id"]
    contour = client.get(f"/api/v1/jobs/{job}/result").json()["result"]
    village_id, point = contour["village_id"], contour["suggested_pond_location"]

    accepted = client.post(
        "/api/v1/analysis/pond-design",
        json={"village_id": village_id, "pour_point": point, "target_reliability": 0.75},
    )
    assert accepted.status_code == 202, accepted.text
    design_job = accepted.json()["job_id"]
    status = client.get(f"/api/v1/jobs/{design_job}").json()
    assert status["status"] == "succeeded", status
    d = client.get(f"/api/v1/analysis/results/pond-design/{design_job}").json()

    # Every headline number carries a unit and a band.
    for key in ("gross_storage", "live_storage", "dead_storage"):
        assert d[key]["unit"] == "m3" and d[key]["uncertainty_pct"] == 20
    assert d["live_storage"]["value"] < d["gross_storage"]["value"]
    assert 2_000 <= d["gross_storage"]["value"] <= 50_000
    dims = d["dimensions"]
    assert 1.5 <= dims["depth"]["value"] <= 3.5, "depth derived, within the search range"
    assert dims["bottom_length"]["value"] >= 5 and dims["side_slope"]["value"] == 2.0
    assert d["eav_curve"][0]["cumulative_volume"]["value"] == 0.0
    assert d["eav_curve"][-1]["cumulative_volume"]["value"] == pytest.approx(
        d["gross_storage"]["value"], rel=1e-3
    )
    assert 0.0 <= d["reliability"]["value"] <= 1.0
    boq = d["bill_of_quantities"]
    assert (
        boq["indicative_cost"]["unit"] == "INR"
        and boq["excavation_volume"]["value"] > d["gross_storage"]["value"]
    )
    assert d["confidence"] in {"low", "moderate", "high"} and "30 m" in d["confidence_rationale"]
    assert d["runoff"]["recommended"]["method"] == "scs_cn"
    assert d["rainfall_summary"]["dependable_75"]["unit"] == "mm/yr"
    codes = {w["code"] for w in d["warnings"]}
    assert {"water_balance", "natural_impoundment", "curve_number_basis"} <= codes
    assert d["catchment"]["snapped_point"]["lon"] == pytest.approx(point["lon"], abs=0.002)
    assert "X-Fixture-Data" not in accepted.headers
