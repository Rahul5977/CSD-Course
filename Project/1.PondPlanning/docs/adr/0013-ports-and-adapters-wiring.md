# ADR 0013 — One code path, three configurations: ports and adapters chosen by settings

**Status:** Accepted · 2026-08-26 · Phase P1

## Context

The same pipeline — upload → parse → DEM → COG → layers — has to run in three
places: the Docker stack (Postgres, Celery on Redis, MinIO), the CI runner and
a laptop without Docker, and the test suite. The usual outcome is a test suite
full of mocks that exercise nothing, and a "works on my machine" gap between
the unit tests and the deployment.

## Decision

Every external dependency sits behind a small **port** (a `Protocol`) with two
**adapters**, and `Settings` picks the adapter once per process:

| Port | Docker adapter | Local / test adapter | Setting |
|---|---|---|---|
| `Repositories` (villages, jobs, DEM assets) | SQLAlchemy on PostGIS | in-memory dictionaries | `POND_PERSISTENCE=postgres\|memory` |
| `JobRunner` | Celery `send_task` over Redis | run the task inline | `POND_JOB_RUNNER=celery\|inline` |
| `ObjectStore` | MinIO (S3) | a directory | `POND_OBJECT_STORE=minio\|local` |
| `DEMProvider` | `ContourKMLAdapter` | same | — (`ProviderTileAdapter` is a documented stub) |

The workflow (`app/engines/workflows/contour_analysis.py`) receives a
`WorkflowContext` holding the chosen adapters and never reads settings itself.
Routers get the same objects through FastAPI dependencies.

## Consequences

- `make check` runs the *real* pipeline on the *real* sample map with no
  Docker, no network and no mocks — `tests/test_contour_job_flow.py` is the
  walking skeleton's proof.
- The in-memory adapters are not test doubles; `make api-dev` runs the whole
  application on them.
- Adding an adapter (a second DEM source, a different queue) is a new class and
  one settings value, not a change to any engine.
- Cost: three small `Protocol`s and their factories, ~250 lines. Every one of
  them is explainable in a sentence.

## Alternatives rejected

- **Mocks in tests.** They test the mock. The bugs this project fears — units,
  CRS, an `ID` field read as elevation — live in the real code path.
- **Conditionals inside engines** (`if settings.env == "ci"`). Scatters the
  wiring decision across the codebase and makes engines depend on settings.
