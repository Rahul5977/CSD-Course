"""FR3 through the API: suitability job → available land + ranked sites (offline providers)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain.errors import UpstreamUnavailableError
from app.engines.workflows import suitability as workflow
from tests.conftest import SAMPLE_KML
from tests.test_runoff_flow import OfflineWorldCover

pytestmark = pytest.mark.skipif(not SAMPLE_KML.exists(), reason="sample map not present")


def _no_sentinel(*args: object, **kwargs: object) -> None:
    msg = "offline"
    raise UpstreamUnavailableError(msg)


def test_suitability_job_yields_parcels_and_ahp_ranked_sites(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workflow, "WorldCoverAdapter", OfflineWorldCover)
    monkeypatch.setattr(workflow, "season_composite", _no_sentinel)
    with SAMPLE_KML.open("rb") as handle:
        job = client.post(
            "/api/v1/analyzeContour", files={"file": (SAMPLE_KML.name, handle)}
        ).json()["job_id"]
    village_id = client.get(f"/api/v1/jobs/{job}/result").json()["result"]["village_id"]

    assert client.get(f"/api/v1/villages/{village_id}/available-land").status_code == 404, (
        "not computed yet"
    )
    accepted = client.post(
        "/api/v1/analysis/suitability", json={"village_id": village_id, "top_n": 5}
    )
    assert accepted.status_code == 202, accepted.text
    sjob = accepted.json()["job_id"]
    status = client.get(f"/api/v1/jobs/{sjob}").json()
    assert status["status"] == "succeeded", status
    result = client.get(f"/api/v1/analysis/results/suitability/{sjob}").json()

    assert result["consistency_acceptable"] and result["consistency_ratio"] < 0.10
    assert sum(result["weights"].values()) == pytest.approx(1.0)
    assert 1 <= len(result["sites"]) <= 5
    top = result["sites"][0]
    assert top["rank"] == 1 and {c["criterion"] for c in top["criteria"]} == set(result["weights"])
    assert sum(c["contribution"]["value"] for c in top["criteria"]) == pytest.approx(
        top["total_score"]["value"], rel=1e-6
    )
    assert any(w["code"] == "ahp_matrix" for w in result["warnings"])
    assert any(w["code"] == "water_mask_fallback" for w in result["warnings"])

    land = client.get(f"/api/v1/villages/{village_id}/available-land").json()
    assert land["total_eligible_area"]["unit"] == "ha" and land["total_eligible_area"]["value"] > 0
    assert "slope < 15 %" in land["constraints_applied"] and any(
        "within 150 m of water" in c for c in land["constraints_applied"]
    )
    assert land["parcels"] and land["parcels"][0]["ownership_class"] == "unknown"
    assert land["geojson"]["features"][0]["geometry"]["type"] in {"Polygon", "MultiPolygon"}
    assert any(w["code"] == "ownership_unknown" for w in land["warnings"])
    layers = {
        layer["layer_id"]
        for layer in client.get(f"/api/v1/terrain/{village_id}/layers").json()["layers"]
    }
    assert {"suitability", "water_mask"} <= layers
    assert "X-Fixture-Data" not in accepted.headers
