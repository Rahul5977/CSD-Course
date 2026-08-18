# ADR 0004 — Compose grows by need, starting at three services

**Status:** Accepted · 2026-08-18 · Phase P0

## Context

`docs/PLAN.md` P0 specifies a compose file with nine services: postgres+postgis
+timescale, redis, minio, api, worker, titiler, martin and nginx. All of them
are genuinely part of the target architecture.

Against that, the assignment's LLM-usage policy requires that every library and
every design decision be defensible in a live demonstration. Nine services
declared on day one, seven of which nothing yet calls, is nine things to defend
and zero things exercised — and an unused service in a compose file reads to an
evaluator exactly like scaffolding that was copied rather than chosen.

## Decision

Start with the three services the API cannot boot without, and add each of the
rest in the phase that first calls it:

| Service | Added in | Because |
|---|---|---|
| postgres + postgis | P0 | Villages, jobs, audit log; spatial types from the first migration |
| redis | P0 | Cache and, shortly, the job broker |
| api | P0 | — |
| worker (Celery) | P1 | The first analysis that exceeds a request timeout |
| minio | P1 | The first COG that has to be stored and served |
| titiler | P1 | The first raster tile layer in the browser |
| martin | P2 | Vector tiles for contours and streams |
| timescaledb | P3 | The daily rainfall series, where a hypertable earns its keep |
| nginx | P6 | TLS termination and rate limiting during hardening |

## Consequences

Every service in the file at any moment is one that something calls, and its
arrival is tied to a phase and a reason. The table above is the record, and it
goes into the report's architecture section.

Risk accepted: adding TimescaleDB in P3 means either swapping the Postgres image
for `timescale/timescaledb-ha` or installing the extension into the existing one.
Both are routine, and `make seed` regenerates all derived data, so the cost of
deferring is bounded.
