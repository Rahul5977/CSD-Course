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


def test_soilgrids_query_uses_published_layers_and_weights_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ask SoilGrids for its published layers and weight them by thickness.

    SoilGrids has 0-5/5-15/15-30 cm layers, not a 0-30 cm one. Response shape recorded
    from the live API at 74.41 E, 18.91 N.
    """
    import io
    import json as _json
    import urllib.request

    from app.providers.landcover import SoilGridsAdapter

    seen: list[str] = []
    doc = {
        "properties": {
            "layers": [
                {
                    "name": "clay",
                    "depths": [
                        {"label": "0-5cm", "values": {"mean": 435}},
                        {"label": "5-15cm", "values": {"mean": 423}},
                        {"label": "15-30cm", "values": {"mean": 426}},
                    ],
                },
                {
                    "name": "sand",
                    "depths": [
                        {"label": "0-5cm", "values": {"mean": 294}},
                        {"label": "5-15cm", "values": {"mean": 301}},
                        {"label": "15-30cm", "values": {"mean": 291}},
                    ],
                },
            ]
        }
    }

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        seen.append(request.full_url)
        return io.BytesIO(_json.dumps(doc).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    texture = SoilGridsAdapter(5).texture(74.41, 18.91)
    assert "depth=0-5cm" in seen[0] and "depth=15-30cm" in seen[0] and "0-30cm" not in seen[0]
    assert texture.clay_pct == pytest.approx((43.5 * 5 + 42.3 * 10 + 42.6 * 15) / 30)
    assert texture.hsg == "D" and texture.assumed is False
