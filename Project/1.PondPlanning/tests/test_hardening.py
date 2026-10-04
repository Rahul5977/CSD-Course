"""P6: idempotency keys, lifecycle with RBAC + audit outbox, exports, WebSocket progress."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.engines.workflows import runoff as runoff_workflow
from app.providers.landcover import DefaultSoilAdapter
from tests.conftest import SAMPLE_KML
from tests.test_runoff_flow import OfflineWorldCover

pytestmark = pytest.mark.skipif(not SAMPLE_KML.exists(), reason="sample map not present")


def _login(client: TestClient, user: str) -> dict[str, str]:
    token = client.post(
        "/api/v1/auth/token", json={"username": user, "password": f"{user}-demo"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def design(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    """A succeeded pond-design job on the sample; returns (village_id, design_job_id)."""
    monkeypatch.setattr(runoff_workflow, "WorldCoverAdapter", OfflineWorldCover)
    monkeypatch.setattr(runoff_workflow, "SoilGridsAdapter", lambda: DefaultSoilAdapter("C"))
    with SAMPLE_KML.open("rb") as handle:
        job = client.post(
            "/api/v1/analyzeContour", files={"contour_map": (SAMPLE_KML.name, handle)}
        ).json()["job_id"]
    contour = client.get(f"/api/v1/jobs/{job}/result").json()["result"]
    accepted = client.post(
        "/api/v1/analysis/pond-design",
        json={
            "village_id": contour["village_id"],
            "pour_point": contour["suggested_pond_location"],
        },
    )
    return contour["village_id"], accepted.json()["job_id"]


def test_idempotency_key_returns_the_same_job(client: TestClient, design: tuple[str, str]) -> None:
    village_id, _ = design
    body = {"village_id": village_id, "pour_point": {"lon": 81.2973, "lat": 21.2519}}
    first = client.post(
        "/api/v1/analysis/catchment", json=body, headers={"Idempotency-Key": "tap-1"}
    ).json()
    second = client.post(
        "/api/v1/analysis/catchment", json=body, headers={"Idempotency-Key": "tap-1"}
    ).json()
    other = client.post(
        "/api/v1/analysis/catchment", json=body, headers={"Idempotency-Key": "tap-2"}
    ).json()
    assert first["job_id"] == second["job_id"] != other["job_id"]


def test_recommendation_lifecycle_is_role_gated_and_audited(
    client: TestClient, design: tuple[str, str]
) -> None:
    _, job_id = design
    # viewer cannot save
    denied = client.post("/api/v1/recommendations", json={"design_job_id": job_id})
    assert denied.status_code == 403 and denied.json()["code"] == "forbidden"
    planner, officer = _login(client, "planner"), _login(client, "officer")
    created = client.post(
        "/api/v1/recommendations", json={"design_job_id": job_id}, headers=planner
    )
    assert created.status_code == 201, created.text
    rec = created.json()
    assert (
        rec["status"] == "draft"
        and rec["gross_storage"]["unit"] == "m3"
        and rec["created_by"] == "planner"
    )
    rid = rec["id"]
    # illegal transition
    bad = client.post(
        f"/api/v1/recommendations/{rid}/status",
        json={"status": "approved", "reason": "skip"},
        headers=officer,
    )
    assert bad.status_code == 409 and bad.json()["code"] == "illegal_transition"
    # planner submits, viewer cannot approve, officer approves
    assert (
        client.post(
            f"/api/v1/recommendations/{rid}/status",
            json={"status": "submitted", "reason": "ready"},
            headers=planner,
        ).json()["status"]
        == "submitted"
    )
    viewer_try = client.post(
        f"/api/v1/recommendations/{rid}/status",
        json={"status": "approved", "reason": "x"},
        headers=_login(client, "viewer"),
    )
    assert viewer_try.status_code == 403
    planner_try = client.post(
        f"/api/v1/recommendations/{rid}/status",
        json={"status": "approved", "reason": "x"},
        headers=planner,
    )
    assert planner_try.status_code == 403, "planner may submit but not approve"
    approved = client.post(
        f"/api/v1/recommendations/{rid}/status",
        json={"status": "approved", "reason": "sanctioned under MGNREGA"},
        headers=officer,
    )
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    # outbox → audit (drain as the beat task would)
    from app.api.deps import get_repositories

    repos = get_repositories()
    trail = client.get(f"/api/v1/recommendations/{rid}/audit").json()
    assert trail["pending_outbox"] == 3 and trail["audit"] == []
    assert repos.outbox.drain(repos.audit.append) == 3
    trail = client.get(f"/api/v1/recommendations/{rid}/audit").json()
    assert trail["pending_outbox"] == 0
    assert [row["action"] for row in trail["audit"]] == [
        "recommendation.created",
        "recommendation.status_changed",
        "recommendation.status_changed",
    ]
    assert trail["audit"][-1]["detail"] == {
        "from": "submitted",
        "to": "approved",
        "reason": "sanctioned under MGNREGA",
    }
    assert trail["audit"][-1]["actor"] == "officer"
    listing = client.get("/api/v1/recommendations").json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == rid


def test_exports_are_generated_and_downloadable(
    client: TestClient, design: tuple[str, str]
) -> None:
    _, job_id = design
    rid = client.post(
        "/api/v1/recommendations", json={"design_job_id": job_id}, headers=_login(client, "planner")
    ).json()["id"]
    for fmt, magic in (
        ("pdf", b"%PDF"),
        ("geojson", b'{"type": "FeatureCollection"'),
        ("csv", b"item,value,method"),
    ):
        desc = client.post(f"/api/v1/recommendations/{rid}/exports?export_format={fmt}").json()
        assert desc["format"] == fmt and desc["size_bytes"] > 100
        download = client.get(desc["url"])
        assert download.status_code == 200 and download.content.startswith(magic), fmt
    assert client.get("/api/v1/exports/3f2a9c1e-5b7d-4e8a-9c1f-2d6b8e4a7c93.pdf").status_code == 404


def test_websocket_streams_job_status_until_terminal(
    client: TestClient, design: tuple[str, str]
) -> None:
    _, job_id = design
    with client.websocket_connect(f"/api/v1/jobs/{job_id}/ws") as ws:
        message = ws.receive_json()
    assert (
        message["job_id"] == job_id
        and message["status"] == "succeeded"
        and message["progress"] == 100
    )


def test_backpressure_answers_429_with_retry_after(
    client: TestClient, design: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import backpressure

    village_id, _ = design
    monkeypatch.setattr(
        backpressure,
        "accept_or_429",
        lambda settings, queue: (_ for _ in ()).throw(
            backpressure.BackpressureError(queue, 25, 75)
        ),
    )
    from app.api.routers import analysis

    monkeypatch.setattr(analysis, "accept_or_429", backpressure.accept_or_429)
    response = client.post(
        "/api/v1/analysis/catchment",
        json={"village_id": village_id, "pour_point": {"lon": 81.2973, "lat": 21.2519}},
    )
    assert response.status_code == 429 and response.headers["Retry-After"] == "75"
    assert response.json()["code"] == "queue_saturated"
