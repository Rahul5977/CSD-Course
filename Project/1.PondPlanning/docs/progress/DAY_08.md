# DAY_08 — 2026-08-26
**Phase:** P7 · **Gate:** G7

## What worked
- Coverage run: engines 94.3 %, domain 97.6 %, api 93.3 %, overall 86.2 % (203 tests). Screenshot `docs/figures/p7-coverage.jpg`.
- README installation guide: prerequisites → `make up` → `make seed` → verification checklist → 14-row troubleshooting table collected from DAY_03–07.
- `docs/api/cookbook.md` with curl per endpoint and 15 trimmed real responses captured from the running stack into `docs/api/samples/`; `errors.md` regenerated from `/meta/errors` (13 codes).
- `docs/report/REPORT.md`: requirements coverage, architecture, stack reconciliation, 12 patterns, methodology per FR, validation table with the measured numbers, limitations, future work, AI-use statement, 20 references.
- `docs/LICENSES.md`, `docs/DEMO.md` (7 minutes, 9 beats, expected questions), `make tunnel`.

## What broke
- `make check` had drifted: `ruff format` on four files and 11 lint findings in `scripts/`, `infra/locustfile.py` and migration 0003 (unused imports, docstrings, long lines). Those files were added in P6 by scripts that skipped the check. Fixed; CI is what should have caught it — it did run on push, so the lesson is to run `make check` before every commit, not after.

- The clean-clone gate check found two install defects invisible on a warm volume: Postgres's initdb temporary server answers `pg_isready` over the unix socket, so the healthcheck passed before the real server was up and the first `alembic upgrade head` was refused; and `beat` crash-looped on `Permission denied: 'celerybeat-schedule'` because the image runs unprivileged. Fixed: healthcheck probes TCP (`-h localhost`), `make up` retries the migration, the schedule file lives in `/tmp`, and `make seed` waits for `/ready` and fails with a message instead of a traceback. Both are now rows in the README troubleshooting table.

## Screenshot
`docs/figures/p7-coverage.jpg`

## Decisions made
- Report in Markdown in the repo (`docs/report/REPORT.md`), not a separate PDF: it is version-controlled, links to the figures, and the submission form accepts a repo link. A PDF export is one `pandoc` away if the form requires it.
- Backup recording = the chaos-test GIF plus the full figure set rather than a fresh screen recording: every demo beat already has a captured artifact; the user can record a run-through on rehearsal.

## Tomorrow's three tasks
1. Rehearse `docs/DEMO.md` three times against `make up && make seed`; time each beat.
2. `make tunnel`, paste the public URL into REPORT.md and Phase 2 submission.
3. Read PLAN.md Part 8 (cheap-marks checklist) once more against the repo.
