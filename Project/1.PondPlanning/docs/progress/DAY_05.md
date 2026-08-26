# DAY_05 — 2026-08-26 (night)
**Phase:** P4 · **Gate:** G4 closed — 7 of 8 FRs real (FR8 overlay polish is P5)

## What worked
- FR3 as one readable Specification expression; every leaf names itself and the response lists the
  rules. Live on the sample: 27 ha eligible in 16 patches, largest 6.75 ha of cropland.
- Sentinel-2 NDWI from three post-monsoon scenes read as COG windows off AWS: Otsu → OpenCV
  open/close → components ≥ 200 m² gives 20 water bodies covering 9.0 % of the area — WorldCover's
  2021 water class says 8.1 %, an independent agreement. Figure: `docs/figures/p4-ndwi-opencv.png`.
- AHP over the four terrain criteria: CR 0.004 for the declared matrix, an intransitive matrix is
  rejected in a golden test; the ranking returns raw value × membership × weight per criterion.
- Commit history scrubbed of AI co-author trailers at the user's request (filter-branch, force-push;
  authors unchanged). The report will still cite AI tool use, as the assignment requires.

## What broke
- Otsu on a two-valued synthetic returns the *lower* mode, which my NDWI > 0 guard then clamps to
  0 — the guard is right (it stops a land-only scene from calling its wetter half "water"); the
  test expectation was wrong.
- A buffer test cell was 80 m from the tank, not 50. Arithmetic, not the engine.
- SoilGrids still times out from inside Docker; the default HSG C path is what runs. Fine, flagged.

## Decisions made
Five rows in the decision log + ADR 0017 (XGBoost/SHAP deferred by the plan's own fallback: two
OSM tanks are not a training set).

## Screenshots
`p4-ndwi-opencv.png`; the UI screenshot is deferred to G5 — Chrome throttled the automation window's WebGL frames tonight (frames only on interaction), so the land panel could not be captured cleanly.

## Tomorrow's three tasks
1. P5 — FR8: the six PDF overlays toggleable together with a stats panel; loading/empty/error/stale
   states on every panel; 390 px layout; plain-language verdicts; screenshot set (rows 22–24).
2. P5 — typed client from OpenAPI (`openapi-typescript`), TanStack-free polling kept simple; service-
   worker tile cache for the chaos test.
3. P6 — bulkhead queues, WebSocket progress, Saga onboarding, idempotency keys, JWT/RBAC, audit
   outbox, metrics + Grafana, backpressure, Locust, the chaos-test video.
