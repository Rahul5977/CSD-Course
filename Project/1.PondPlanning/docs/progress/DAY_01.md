# DAY_01 — 2026-08-18
**Phase:** P0 — Foundations & Contract · **Gate:** G0 (open)

## What worked

P0 chunk 1 landed and is verified end to end on a clean slate.

- **Layered package tree** under `app/`: `api schemas engines domain providers
  repositories jobs reports core`. Every package's `__init__.py` states its own
  layering rule in its docstring, so the constraint is visible where it is
  violated rather than only in a document.
- **`tests/test_layering.py`** enforces that mechanically by parsing the AST:
  no framework import inside `domain`/`engines`, no outward import between
  layers, no handler in `api/` over 25 statements. This is the artifact for the
  3 "layered architecture" marks — a convention nobody checks is a convention
  that decays, and it is far more convincing to an evaluator than prose.
- **Tooling:** uv + committed `uv.lock`, ruff (format + lint, with pydocstyle so
  engines must document their algorithm), `mypy` strict on `app/domain` and
  `app/engines`, pytest with `golden` and `integration` markers already declared.
- **`infra/docker-compose.yml`** — postgres+postgis, redis, api. Multi-stage
  `Dockerfile.api`, non-root user, container healthcheck.
- **Alembic revision 0001** — postgis extension, `villages` (MultiPolygon,
  SRID 4326), `jobs`, `audit_log`.
- **`Makefile`** with 15 targets, and **GitHub Actions CI** running format, lint,
  types, tests, plus an image build.
- **ADRs 0001–0004** written: layered architecture, Python/uv pinning, sync
  SQLAlchemy, and compose-grows-by-need.

Verified, not assumed:

```
make down ARGS=-v && make up     -> clean bring-up in 15 s, migration applied
make check                       -> ruff clean · mypy clean (23 files) · 15 passed
GET /health                      -> 200 {"status":"ok", ... "env":"docker"}
GET /ready                       -> 200 {"status":"ready", deps: postgres reachable}
GET /docs, /openapi.json         -> 200
```

## What broke

Four things, all caught by actually running the stack rather than by reading it.

1. **The image would not build.** `hatchling` needs the file named in
   `readme = "README.md"`, and the Dockerfile never copied it. A `.dockerignore`
   negation (`!README.md`) is not enough — the file still has to be `COPY`d.
2. **ruff sorted `app` before `fastapi`.** `src = ["app", "tests"]` was the wrong
   knob; `known-first-party = ["app"]` is the right one.
3. **Alembic autogenerate wanted to drop forty tables.** The `postgis/postgis`
   image installs the tiger geocoder and topology extensions and puts `tiger` on
   the database search_path, so autogenerate saw extension-owned tables as
   orphans. Fixed with a strict `include_object`: a *reflected* table this
   metadata does not declare is not ours, so we neither create nor drop it. This
   would have been a genuinely nasty surprise in P3 when the rainfall tables land.
4. **ORM/migration drift on day one.** The two `CHECK` constraints on `jobs`
   existed in the migration but not in the model. Autogenerate found it
   immediately. Re-running it now produces an empty `upgrade()` — which is the
   real proof that the model and the schema agree.

## Screenshot

Not captured yet. Swagger currently lists only `/health` and `/ready`, so the
evidence-register screenshot (row 5) is worth taking after chunk 2 puts the ~25
contract endpoints on the page.

## Decisions made

Mirrored into the `docs/PROGRESS.md` decision log, and each has an ADR:

- Layered architecture **enforced by an executable test**, not by convention (ADR 0001).
- **Python 3.12**, not the 3.14 on this machine — numba/pysheds/rasterio wheels
  lag, and finding that out mid-P2 would cost a day (ADR 0002).
- **Synchronous SQLAlchemy on psycopg3.** The heavy work is raster processing in
  a worker, not database I/O; async buys nothing measurable here and adds a bug
  class (a blocking call stalling the event loop) that presents as "sometimes
  slow" rather than as an error (ADR 0003).
- **Compose starts at 3 services, not PLAN.md's 9,** with each remaining service
  tied to the phase that first calls it. Every service in the file is one
  something actually uses — which is also the honest answer in a viva (ADR 0004).
- **`audit_log` is append-only in the database**, via `DO INSTEAD NOTHING` rules,
  not merely by convention. Verified: `UPDATE` and `DELETE` both affect 0 rows
  and the original row survives unchanged. A trail the application can rewrite is
  not evidence.

## Tomorrow's three tasks

1. **P0 chunk 2:** define the ~25 contract endpoints as FastAPI routes returning
   realistic fixtures — especially the full `pond-design` payload. This is the
   parallelism unlock; skipping it blocks the frontend until P4.
2. Write ADRs 0005–0012, and capture the Swagger screenshot once the routes are
   on the page (evidence register rows 3 and 5).
3. **Choose the village** (`docs/PROGRESS.md` blocker 2). P1 cannot start without a
   boundary, and FR7 validation needs an existing pond nearby to compare against.
