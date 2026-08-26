# DAY_06 — 2026-08-27 (early)
**Phase:** P5 · **Gate:** G5 closed — all 8 FRs demonstrable from the browser

## What worked
- FR8 as a results overlay pinned to the map with the six PDF items, and the designed pond drawn
  as a footprint at the outlet; a focus mask dims imagery outside the analysed boundary (FR1's
  "clipped to the boundary" reading).
- Every long action now shows the worker's stage and percentage — the same `stage` string the
  API returns — so a 60 s suitability job reads as progress, not silence.
- Offline-first service worker: tiles cache-first, API network-first with a stale fallback and a
  header badge (ADR 0018). This is the P6 chaos test's client half.
- Generated OpenAPI types for the envelopes; an EN/HI toggle; 390 px layout.

## What broke
- The map's first frame was not painted because the container is laid out by CSS grid after the
  map is constructed; `map.resize()` on load + a ResizeObserver fixed it — and the automation
  window is throttled by Chrome, so frames arrive only on interaction during captures.

## Screenshots
`docs/figures/p5-all-overlays.jpg`, `p5-phone-390px.jpg`

## Tomorrow's three tasks
1. P6 day 1: bulkhead queues, WebSocket progress, Saga onboarding, idempotency keys, JWT/RBAC,
   site state machine, outbox → audit log.
2. P6 day 2: structured logs with correlation ids, Prometheus + Grafana, leader-elected refresh,
   backpressure 429, Locust p95, chaos-test video.
3. P7: coverage ≥ 70 %, install guide with troubleshooting, API cookbook, report, demo rehearsal.
