"""Locust load test: 50 users clicking catchments on the seeded village (P6, evidence row 27).

    uv run locust -f infra/locustfile.py --headless -u 50 -r 10 -t 60s --host http://localhost:8000

Each user picks a random point inside the village extent, submits a
catchment job with an Idempotency-Key, polls to completion and records the
end-to-end time as a custom metric, so the p95 reported is the number an
administrator waits — not just the 202.
"""

from __future__ import annotations

import json
import random
import time
import uuid

from locust import HttpUser, between, events, task


class Planner(HttpUser):
    """A planner clicking around the map."""

    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        """Pick the first seeded village and its extent."""
        villages = self.client.get("/api/v1/villages").json()["items"]
        self.village_id = villages[0]["id"]
        ring = villages[0]["boundary"]["coordinates"][0]
        ring = ring[0] if isinstance(ring[0][0], list) else ring
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        self.bounds = (min(lons), min(lats), max(lons), max(lats))

    @task(5)
    def catchment(self) -> None:
        """Submit and wait for a catchment."""
        w, s, e, n = self.bounds
        point = {"lon": random.uniform(w + 0.002, e - 0.002), "lat": random.uniform(s + 0.002, n - 0.002)}
        started = time.perf_counter()
        accepted = self.client.post(
            "/api/v1/analysis/catchment",
            json={"village_id": self.village_id, "pour_point": point},
            headers={"Idempotency-Key": str(uuid.uuid4())},
            name="POST catchment",
        )
        if accepted.status_code != 202:
            return
        job_id = accepted.json()["job_id"]
        status = "queued"
        for _ in range(60):
            status = self.client.get(f"/api/v1/jobs/{job_id}", name="GET job").json()["status"]
            if status in {"succeeded", "failed"}:
                break
            time.sleep(0.5)
        elapsed_ms = (time.perf_counter() - started) * 1000
        events.request.fire(
            request_type="E2E", name="catchment end-to-end", response_time=elapsed_ms,
            response_length=0, exception=None if status == "succeeded" else RuntimeError(status),
        )  # fmt: skip

    @task(2)
    def rainfall(self) -> None:
        """A cached read."""
        self.client.get("/api/v1/rainfall/statistics?lon=81.297&lat=21.2517", name="GET rainfall")

    @task(1)
    def layers(self) -> None:
        """Layer list."""
        self.client.get(f"/api/v1/terrain/{self.village_id}/layers", name="GET layers")
