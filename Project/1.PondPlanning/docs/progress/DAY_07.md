# DAY_07 — 2026-08-27
**Phase:** P6 · **Gate:** G6 closed — 91/100 accounted for

## What worked
- Bulkheads in one live sentence: with a suitability job at 10 % on the heavy queue, a catchment
  click on the interactive queue returned in 0.6 s.
- Locust, 50 users for 60 s: 1 102 catchment submissions, POST p95 33 ms, end-to-end p95 560 ms,
  0 HTTP failures, 88 req/s aggregate on a laptop under Docker (`docs/figures/p6-locust.txt`).
- The saga rolled back a half-registered village on an injected object-store failure at step 2,
  and the job record names the failed step and what was compensated.
- Recommendation lifecycle end to end under RBAC: viewer 403, planner submits, officer approves,
  outbox drained to the append-only audit log, PDF/GeoJSON/CSV exports downloadable.
- Prometheus scraping the API and both workers; the provisioned Grafana dashboard shows queue
  depth, job p50/p95, provider errors, cache hit rate and HTTP p95 (`docs/figures/p6-grafana.jpg`).
- Chaos test: stop the API container, reload — village, layers, rainfall and design still shown
  from the service-worker cache with the offline badge (`docs/media/chaos-test.gif`).

## What broke
- A saga step that fails half-way is not "completed", so its compensation never ran — partial
  raster uploads survived. Steps now clean their own partial work before re-raising.
- The generated OpenAPI types rejected two hand-typed frontend shortcuts (`created_at` missing,
  `error` not a problem document). Correct on both counts.
- The single `worker` container survived the split as an orphan; `docker compose up --remove-orphans`
  → troubleshooting row.
- 14 of 1 093 Locust end-to-end samples "failed": random points with no channel within 150 m —
  the engine's honest refusal (`no modelled drainage`), recorded as such.

## Decisions made
ADR 0019 + three decision-log rows.

## Tomorrow's three tasks
1. P7 — coverage ≥ 70 % on `engines/` + `domain/` (screenshot), test taxonomy check, `make check` clean.
2. P7 — README installation guide (prereqs → `make up` → `make seed` → verification → ≥ 6-row
   troubleshooting table), API cookbook + error catalogue, licence register.
3. P7 — technical report with citations and the validation section; `make seed` offline demo;
   rehearse 3×, backup recording, `git tag v1.0`.
