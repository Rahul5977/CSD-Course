"""Saga orchestration for multi-step jobs with compensation (P6).

A job that writes to three stores (Postgres, MinIO, the job row) can fail
half-way and leave a village with a DEM asset but no rasters. The **Saga**
pattern runs the steps in order and, on failure, runs each completed step's
*compensation* in reverse, so the system returns to a consistent state and
the job record says exactly what was undone.

Each step is **idempotent** (skip-if-exists): re-running a job after a crash
does not duplicate a village or re-upload a raster that is already there.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

Action = Callable[[dict[str, Any]], Any]
Compensation = Callable[[dict[str, Any]], None]
Exists = Callable[[dict[str, Any]], bool]


@dataclass(frozen=True, slots=True)
class Step:
    """One saga step: do it, know whether it is already done, and undo it."""

    name: str
    action: Action
    compensate: Compensation | None = None
    already_done: Exists | None = None


@dataclass
class SagaRun:
    """What happened: completed steps in order, skipped ones, and any compensation."""

    completed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    compensated: list[str] = field(default_factory=list)
    failed_step: str | None = None
    error: str | None = None


class SagaError(Exception):
    """Raised after compensation so the caller sees the original failure and the run."""

    def __init__(self, run: SagaRun, cause: BaseException) -> None:
        """Keep the run record and the cause."""
        super().__init__(f"saga failed at {run.failed_step}: {cause}")
        self.run = run
        self.cause = cause


class Saga:
    """Run steps forward; on failure, compensate completed steps in reverse."""

    def __init__(self, steps: list[Step], on_progress: Callable[[str], None] | None = None) -> None:
        """``on_progress`` receives each step's name as it starts."""
        self._steps = steps
        self._on_progress = on_progress or (lambda _name: None)

    def execute(self, ctx: dict[str, Any]) -> SagaRun:
        """Run every step, sharing ``ctx`` between them.

        Raises:
            SagaError: If a step fails, after compensations have run.
        """
        run = SagaRun()
        done: list[Step] = []
        for step in self._steps:
            self._on_progress(step.name)
            try:
                if step.already_done and step.already_done(ctx):
                    run.skipped.append(step.name)
                    continue
                step.action(ctx)
                run.completed.append(step.name)
                done.append(step)
            except Exception as exc:
                run.failed_step = step.name
                run.error = f"{type(exc).__name__}: {exc}"
                logger.warning("saga step failed", extra={"step": step.name, "error": str(exc)})
                for finished in reversed(done):
                    if finished.compensate is None:
                        continue
                    try:
                        finished.compensate(ctx)
                        run.compensated.append(finished.name)
                    except Exception as comp_exc:  # compensation must never mask the cause
                        logger.error(
                            "compensation failed",
                            extra={"step": finished.name, "error": str(comp_exc)},
                        )
                raise SagaError(run, exc) from exc
        return run
