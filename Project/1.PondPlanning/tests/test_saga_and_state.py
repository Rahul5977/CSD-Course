"""Saga compensation order, idempotent skips, and the recommendation state machine."""

from __future__ import annotations

import pytest

from app.domain.recommendation import (
    IllegalTransitionError,
    required_role,
    role_allows,
    transition,
)
from app.engines.workflows.saga import Saga, SagaError, Step


def test_saga_compensates_completed_steps_in_reverse_and_reports() -> None:
    log: list[str] = []
    steps = [
        Step("a", lambda c: log.append("do a"), lambda c: log.append("undo a")),
        Step("b", lambda c: log.append("do b"), lambda c: log.append("undo b")),
        Step(
            "c",
            lambda c: (_ for _ in ()).throw(RuntimeError("boom")),
            lambda c: log.append("undo c"),
        ),
        Step("d", lambda c: log.append("do d")),
    ]
    with pytest.raises(SagaError) as excinfo:
        Saga(steps).execute({})
    run = excinfo.value.run
    assert log == ["do a", "do b", "undo b", "undo a"], "reverse order, c never ran so never undone"
    assert run.completed == ["a", "b"] and run.compensated == ["b", "a"]
    assert run.failed_step == "c" and "boom" in (run.error or "")


def test_saga_skips_steps_that_already_happened() -> None:
    log: list[str] = []
    ctx = {"village": True}
    steps = [
        Step(
            "village", lambda c: log.append("create"), already_done=lambda c: bool(c.get("village"))
        ),
        Step("raster", lambda c: log.append("upload")),
    ]
    run = Saga(steps).execute(ctx)
    assert run.skipped == ["village"] and run.completed == ["raster"] and log == ["upload"]


def test_state_machine_allows_the_lifecycle_and_nothing_else() -> None:
    transition("draft", "submitted")
    transition("submitted", "approved")
    transition("submitted", "rejected")
    transition("rejected", "draft")
    for current, target in [
        ("draft", "approved"),
        ("approved", "draft"),
        ("approved", "submitted"),
        ("draft", "rejected"),
    ]:
        with pytest.raises(IllegalTransitionError) as excinfo:
            transition(current, target)
        assert excinfo.value.code == "illegal_transition"


def test_roles_gate_transitions() -> None:
    assert required_role("submitted", "approved") == "officer"
    assert required_role("draft", "submitted") == "planner"
    assert role_allows("officer", "planner") and not role_allows("viewer", "planner")
    assert not role_allows("planner", "officer")
