# ADR 0019 — Hardening: bulkheads, saga, outbox, JWT/RBAC, backpressure, observability

**Status:** Accepted · 2026-08-27 · Phase P6

## Context

The rubric's System Design bucket (15 marks) grades async architecture,
resilience, data design, security, observability, DevOps and scalability
reasoning. The user chose the full P6 scope despite the viva surface, on the
condition that every piece is exercised, not declared.

## Decisions (each exercised by a test or a demo)

1. **Bulkhead queues.** `interactive` (catchment, runoff, design; seconds)
   and `heavy` (contour analysis, suitability; minutes, external reads) with
   separate worker pools, so a village preparation cannot delay a click.
   Demo: submit a suitability job, then a catchment — the catchment returns
   in ~1 s while the heavy job runs.
2. **WebSocket progress (Observer).** `GET /jobs/{id}/ws` watches the job row
   the worker writes and pushes a frame only when status/progress/stage
   change; the client falls back to polling. One source of truth, two views.
3. **Saga for village onboarding.** The contour pipeline's persistence
   (village → rasters → streams → DEM asset) runs as idempotent steps with
   compensations (delete village / objects / asset) executed in reverse on
   failure; the job records `failed_step` and `compensated`. Tested with an
   injected failure at step 3.
4. **Idempotency keys.** `Idempotency-Key` on every analysis POST returns the
   original job for a repeated key (unique index on `jobs`). The frontend sends
   a fresh UUID per user action.
5. **JWT RS256 + RBAC.** 15-minute access / 7-day refresh tokens; roles
   `viewer < planner < officer`; `require_role` on saving and on state
   transitions; a viewer receives `403`. Keys from PEM files or an ephemeral
   pair with a start-up warning, so `make up` never fails for want of a key.
6. **State machine + transactional outbox → audit log.** Recommendation
   status moves are validated by a transition table (`409 illegal_transition`
   otherwise), gated by role, and written with an outbox event that the beat
   task drains into `audit_log`, which is append-only by database rule
   (migration 0001). `GET /recommendations/{id}/audit` shows the trail.
7. **Backpressure.** A queue deeper than `POND_MAX_QUEUE_DEPTH` answers
   `429 queue_saturated` with `Retry-After` rather than piling on.
8. **Observability.** `X-Request-ID` correlation in every JSON log line (the
   worker sets it to the job id), Prometheus metrics (HTTP, job durations,
   provider errors, cache events, queue depth, 429s) scraped from the API and
   both workers, one provisioned Grafana dashboard. Workers run the threads
   pool so the exporter lives in the same process as the jobs (prefork children
   keep separate registries and would report nothing).
9. **Leader-elected nightly rainfall refresh.** Celery beat schedules it; a
   Redis `SET NX EX` lock ensures exactly one worker runs it — the answer to
   "what if you run ten workers?".
10. **nginx hardening.** Per-client rate limits (20 r/s API, 2 r/s uploads),
    security headers, WebSocket upgrade on `/jobs/`.
11. **Offline-first client** (ADR 0018) is the resilience story's visible
    half; the `Cached` provider decorator is the server half.

## Consequences

Nine compose services, each called by something and each demonstrable in a
sentence. The viva surface is larger, as the user accepted; the compensation
is that every claim in the report's system-design section has a test or a
recorded demo behind it (evidence rows 25–28).
