# DAY_10 — 2026-08-31
**Phase:** Phase 2 submission readiness · **Gate:** post-G8 polish

## What worked
- The professor's edge case, end to end: an existing river is now *hard-excluded* from
  siting (not just scored down) and the API says so — `existing_watercourse` warning naming
  the 416 ha channel on the sample. Golden tests for the river and for flat terrain.
- `make e2e`: 42 HTTP checks over every real route plus the negative paths — 42/42 against
  the Docker stack **and** 42/42 against the lab-VM deployment.
- Deployed on the provided lab machine without Docker (it's an unprivileged container):
  `scripts/single_server.py` serves API + SPA from one uvicorn process with the memory/
  inline/local adapters. **Working URL: http://10.1.75.53:4269** (docs at `/docs`).
- Report: new "computation as a graph algorithm" section with four figures generated from
  the real engine (`make figures`), an edge-case table, the deployment story, expanded AI
  usage; simple steel-blue colour grading; PDF re-rendered.

## What broke
- The venv survived the project-folder move with dead shebangs — `uv run mypy` failed with
  *Failed to spawn*. Fixed by recreating; README troubleshooting row added.
- `/ready` reported the healthy no-Docker deployment as degraded forever (it probed postgres
  and redis unconditionally). Now probes only the configured adapters, with tests.
- Starlette raises 404 as an exception from StaticFiles, so the SPA fallback never fired —
  `/app` 404'd on the VM until caught.
- `pkill -f "uvicorn scripts.single_server"` matched the ssh session's own command line and
  killed it (exit 255). Escaped the pattern (`scripts[.]single_server`).
- `# syntax=docker/dockerfile:1` made every build fetch from Docker Hub, which the campus
  network intermittently resets — pins removed, builds work from cache.

## Screenshot
`docs/figures/deploy-vm-swagger.jpg`, `deploy-vm-landing.jpg`, `deploy-vm-workspace.jpg`,
`docs/figures/alg-*.png`

## Decisions made
Mirrored into the decision log: river hard-exclusion bound; configured-adapter readiness;
one-process lab-VM deployment; syntax-pin removal; e2e-as-deployment-gate.

## Tomorrow's three tasks
1. Make the GitHub repo public (or add the professor as collaborator) — the report links it.
2. Rehearse `docs/DEMO.md` from the landing page, using the lab-VM URL as the opener.
3. Re-check the VM server is alive before the demo (`curl http://10.1.75.53:4269/health`;
   restart with `~/pond/run.sh` over ssh if needed).
