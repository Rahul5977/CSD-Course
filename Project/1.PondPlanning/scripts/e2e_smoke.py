"""End-to-end smoke test of every real API route against a running stack.

Run:  uv run python scripts/e2e_smoke.py [BASE_URL]

Walks the whole cookbook in order — upload the sample KML, poll the job, read
the result, then terrain, catchment, rainfall, runoff, pond design,
suitability, auth, the recommendation lifecycle with exports, and the negative
paths (403 for a viewer, 409 for an illegal transition, 404, unsupported
upload). Prints one PASS/FAIL line per check and exits non-zero on any FAIL,
so it doubles as a deployment gate: `make e2e` after `make up && make seed`.

This is deliberately *not* pytest: it exercises a deployed stack over HTTP
exactly the way the browser and the evaluator do, docker or not.
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx2 as httpx

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
API = f"{BASE}/api/v1"
SAMPLE = Path(__file__).resolve().parent.parent / "data" / "samples" / "contours_1m.kml"

client = httpx.Client(timeout=120.0)
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    """Record and print one PASS/FAIL line."""
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL':4}  {name}" + (f"  — {detail}" if detail else ""))


def poll_job(job_id: str, timeout_s: float = 300.0) -> dict[str, Any]:
    """Poll a job envelope until it settles or the timeout passes."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        job = client.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("succeeded", "failed"):
            return job
        time.sleep(2)
    return {"status": "timeout"}


def main() -> int:
    """Run every check in cookbook order; return 1 if any failed."""
    # -- operations ----------------------------------------------------
    r = client.get(f"{BASE}/health")
    check("GET /health", r.status_code == 200, r.json().get("app", ""))
    r = client.get(f"{BASE}/ready")
    check("GET /ready", r.status_code == 200)
    r = client.get(f"{BASE}/metrics")
    check("GET /metrics", r.status_code == 200 and b"http_requests" in r.content)
    r = client.get(f"{API}/meta/implementation-status")
    fixtures = r.json().get("fixture_backed", ["?"])
    check("GET /meta/implementation-status", r.status_code == 200, f"fixtures: {fixtures}")
    r = client.get(f"{API}/meta/errors")
    check("GET /meta/errors", r.status_code == 200 and len(r.json().get("errors", [])) > 5)

    # -- the Phase 2 route --------------------------------------------
    with SAMPLE.open("rb") as f:
        r = client.post(
            f"{API}/analyzeContour",
            files={"file": (SAMPLE.name, f, "application/vnd.google-earth.kml+xml")},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
    check(
        "POST /analyzeContour -> 202",
        r.status_code == 202,
        f"job {r.json().get('job_id', '?')[:8]}",
    )
    job_id = r.json()["job_id"]
    job = poll_job(job_id)
    check("job succeeds", job["status"] == "succeeded", f"stage {job.get('stage')}")
    r = client.get(f"{API}/analysis/results/contour/{job_id}")
    contour = r.json()
    vid = contour["village_id"]
    pond = contour["suggested_pond_location"]
    codes = [w["code"] for w in contour.get("warnings", [])]
    check(
        "GET /analysis/results/contour/{job}",
        r.status_code == 200 and len(contour["candidate_sites"]) >= 1,
        f"village {contour['village_name']}, catchment {contour['catchment']['area']['display']}",
    )
    check(
        "existing watercourse edge case is reported",
        "existing_watercourse" in codes,
        f"warnings: {codes}",
    )

    # -- unsupported upload is a clean 4xx, not a 500 -------------------
    r = client.post(f"{API}/analyzeContour", files={"file": ("x.txt", b"not a map", "text/plain")})
    check(
        "POST /analyzeContour (garbage) -> 4xx problem",
        400 <= r.status_code < 500,
        f"{r.status_code} {r.json().get('code', '')}",
    )

    # -- villages and terrain ------------------------------------------
    for path, name in [
        ("/villages", "GET /villages"),
        (f"/villages/{vid}/summary", "GET /villages/{id}/summary"),
        (f"/villages/{vid}/imagery", "GET /villages/{id}/imagery"),
        (f"/villages/{vid}/siting", "GET /villages/{id}/siting"),
        (f"/terrain/{vid}/layers", "GET /terrain/{id}/layers"),
        (f"/terrain/{vid}/dem", "GET /terrain/{id}/dem"),
        (f"/terrain/{vid}/contours?interval=5", "GET /terrain/{id}/contours"),
        (f"/terrain/{vid}/streams", "GET /terrain/{id}/streams"),
        (f"/terrain/{vid}/derived/twi", "GET /terrain/{id}/derived/twi"),
        (f"/terrain/{vid}/derived/slope", "GET /terrain/{id}/derived/slope"),
    ]:
        r = client.get(f"{API}{path}")
        check(name, r.status_code == 200)

    r = client.get(f"{API}/villages/{uuid.uuid4()}/summary")
    check("GET missing village -> 404 problem", r.status_code == 404, r.json().get("code", ""))

    # -- catchment (FR4) -----------------------------------------------
    r = client.post(
        f"{API}/analysis/catchment",
        json={"village_id": vid, "pour_point": pond},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    check("POST /analysis/catchment -> 202", r.status_code == 202)
    catchment_job = r.json()["job_id"]
    job = poll_job(catchment_job)
    r = client.get(f"{API}/analysis/results/catchment/{catchment_job}")
    check(
        "GET /analysis/results/catchment/{job}",
        job["status"] == "succeeded" and r.status_code == 200,
        r.json()["area"]["display"],
    )

    # -- rainfall (FR5) ------------------------------------------------
    r = client.get(
        f"{API}/rainfall/statistics", params={"lon": pond["lon"], "lat": pond["lat"], "years": 30}
    )
    stats_ok = r.status_code == 200
    check(
        "GET /rainfall/statistics",
        stats_ok,
        r.json()["dependable_75"]["display"] if stats_ok else str(r.status_code),
    )
    r = client.get(
        f"{API}/rainfall/series",
        params={"lon": pond["lon"], "lat": pond["lat"], "start": "2019-06-01", "end": "2019-09-30"},
    )
    check("GET /rainfall/series", r.status_code == 200)

    # -- runoff (FR6) --------------------------------------------------
    r = client.post(
        f"{API}/analysis/runoff",
        json={"village_id": vid, "catchment_job_id": catchment_job, "years": 20},
    )
    check("POST /analysis/runoff -> 202", r.status_code == 202)
    runoff_job = r.json()["job_id"]
    job = poll_job(runoff_job)
    r = client.get(f"{API}/analysis/results/runoff/{runoff_job}")
    check(
        "GET /analysis/results/runoff/{job}",
        job["status"] == "succeeded" and r.status_code == 200,
        f"recommended: {r.json().get('recommended', '?')}" if r.status_code == 200 else "",
    )

    # -- pond design (FR7) ---------------------------------------------
    r = client.post(
        f"{API}/analysis/pond-design",
        json={"village_id": vid, "pour_point": pond, "target_reliability": 0.75},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    check("POST /analysis/pond-design -> 202", r.status_code == 202)
    design_job = r.json()["job_id"]
    job = poll_job(design_job)
    r = client.get(f"{API}/analysis/results/pond-design/{design_job}")
    design_ok = job["status"] == "succeeded" and r.status_code == 200
    check(
        "GET /analysis/results/pond-design/{job}",
        design_ok,
        r.json()["gross_storage"]["display"] if design_ok else "",
    )

    # -- suitability (FR3) ---------------------------------------------
    # With the inline job runner the Sentinel-2 read happens inside this request.
    r = client.post(
        f"{API}/analysis/suitability", json={"village_id": vid, "top_n": 8}, timeout=600.0
    )
    check("POST /analysis/suitability -> 202", r.status_code == 202)
    suit_job = r.json()["job_id"]
    job = poll_job(suit_job, timeout_s=420.0)
    r = client.get(f"{API}/analysis/results/suitability/{suit_job}")
    cr = (r.json().get("ahp") or {}).get("consistency_ratio") if r.status_code == 200 else None
    check(
        "GET /analysis/results/suitability/{job}",
        job["status"] == "succeeded" and r.status_code == 200,
        f"CR {cr:.3f}" if isinstance(cr, float) else "",
    )
    r = client.get(f"{API}/villages/{vid}/available-land")
    check("GET /villages/{id}/available-land", r.status_code == 200)

    # -- auth + recommendation lifecycle -------------------------------
    def token(username: str, password: str) -> str:
        r = client.post(f"{API}/auth/token", json={"username": username, "password": password})
        return str(r.json()["access_token"])

    planner = token("planner", "planner-demo")
    officer = token("officer", "officer-demo")
    viewer = token("viewer", "viewer-demo")
    check("POST /auth/token (3 roles)", bool(planner and officer and viewer))

    r = client.post(
        f"{API}/recommendations",
        json={"design_job_id": design_job},
        headers={"Authorization": f"Bearer {planner}"},
    )
    rec_ok = r.status_code in (200, 201)
    rec = r.json().get("id", "") if rec_ok else ""
    check("POST /recommendations (planner)", rec_ok, f"rec {rec[:8]}")

    r = client.post(
        f"{API}/recommendations/{rec}/status",
        json={"status": "approved", "reason": "skip review"},
        headers={"Authorization": f"Bearer {officer}"},
    )
    check(
        "draft -> approved is 409 illegal_transition",
        r.status_code == 409,
        r.json().get("code", ""),
    )

    r = client.post(
        f"{API}/recommendations/{rec}/status",
        json={"status": "submitted", "reason": "ready"},
        headers={"Authorization": f"Bearer {planner}"},
    )
    check("planner submits", r.status_code == 200)

    r = client.post(
        f"{API}/recommendations/{rec}/status",
        json={"status": "approved", "reason": "viewer tries"},
        headers={"Authorization": f"Bearer {viewer}"},
    )
    check("viewer approve -> 403", r.status_code == 403, r.json().get("code", ""))

    r = client.post(
        f"{API}/recommendations/{rec}/status",
        json={"status": "approved", "reason": "checked"},
        headers={"Authorization": f"Bearer {officer}"},
    )
    check("officer approves", r.status_code == 200)

    r = client.get(f"{API}/recommendations/{rec}/audit")
    check(
        "GET /recommendations/{id}/audit",
        r.status_code == 200
        and len(r.json().get("events", r.json() if isinstance(r.json(), list) else [])) >= 0,
    )

    for fmt in ("pdf", "geojson", "csv"):
        r = client.post(
            f"{API}/recommendations/{rec}/exports",
            params={"export_format": fmt},
            headers={"Authorization": f"Bearer {planner}"},
        )
        check(f"POST exports {fmt}", r.status_code in (200, 201, 202), str(r.status_code))

    # -- summary -------------------------------------------------------
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed against {BASE}")
    if failed:
        print("FAILED:", *failed, sep="\n  - ")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
