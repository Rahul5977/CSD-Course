# Contributing

Conventions for this repository. Git hygiene is directly assessed (Code quality:
version control, 2 marks), so these are not decoration.

## Commit messages — Conventional Commits 1.0.0

```
<type>(<scope>): <subject>

<body — why, not what>
```

`<type>` is one of:

| Type | Use for |
|---|---|
| `feat` | A new capability visible to a user or an API client |
| `fix` | A defect repair |
| `docs` | Documentation, ADRs, the daily progress log |
| `test` | Adding or correcting tests |
| `refactor` | Behaviour-preserving restructuring |
| `perf` | A performance change, with the measurement in the body |
| `build` | Dependencies, Dockerfile, Makefile, CI |
| `chore` | Anything else that touches no source |

`<scope>` is the package or subsystem: `api`, `domain`, `engines`, `providers`,
`repositories`, `infra`, `docs`, `web`.

Subject line: imperative mood, no trailing full stop, ≤ 72 characters.

```
feat(engines): delineate catchment by D8 upslope BFS from a snapped pour point
fix(providers): reject the numeric ID field when reading contour elevations
docs(adr): record why D8 was chosen over D-infinity
```

The body carries the reasoning. A commit that makes a non-obvious modelling
choice must also add a row to the `PROGRESS.md` decision log in the same commit —
that log is the source for the report and the viva.

## Branches

Trunk-based. Work on `main` unless a change is large enough to want review, in
which case `feat/<short-name>` and a pull request.

## Before you push

```bash
make check      # ruff format + ruff check + mypy + pytest — the same as CI
```

CI runs the same three tools. A red build on `main` is fixed before anything
else is started.

## Definition of done

From `the working agreement`, restated here because it is easy to skip:

- `ruff` clean, `mypy --strict` clean on `app/domain` and `app/engines`
- New engine code has unit tests; hydrology changes have a golden test
- **The feature is reachable from the browser**, not only from pytest
- The docstring names the algorithm or pattern implemented
- Every numeric output carries its unit and an uncertainty statement

## Never commit

Secrets (`.env`, keys), generated rasters, DEM tiles, or anything above a few
megabytes. `.gitignore` covers the known cases; if you add a new artifact type,
add a rule in the same commit.
