"""Recommendation lifecycle as an explicit state machine (P6).

States: ``draft → submitted → approved | rejected``. A rejected
recommendation may be reworked (``rejected → draft``). Every other move is
illegal and raises, so "approve an unverified site" cannot happen by
accident — the transition table *is* the policy, and it is tested.
"""

from __future__ import annotations

from typing import Literal

from app.domain.errors import DomainError

RecommendationStatus = Literal["draft", "submitted", "approved", "rejected"]

TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"submitted"}),
    "submitted": frozenset({"approved", "rejected"}),
    "approved": frozenset(),
    "rejected": frozenset({"draft"}),
}

#: Which role may perform which transition.
ROLE_FOR_TRANSITION: dict[tuple[str, str], str] = {
    ("draft", "submitted"): "planner",
    ("submitted", "approved"): "officer",
    ("submitted", "rejected"): "officer",
    ("rejected", "draft"): "planner",
}

ROLE_RANK = {"viewer": 0, "planner": 1, "officer": 2}


class IllegalTransitionError(DomainError):
    """The requested status change is not allowed from the current state."""

    code = "illegal_transition"


def transition(current: str, target: str) -> None:
    """Validate a move; raise :class:`IllegalTransitionError` if it is not allowed."""
    if target not in TRANSITIONS.get(current, frozenset()):
        msg = f"cannot move a recommendation from {current} to {target}"
        raise IllegalTransitionError(
            msg, {"from": current, "to": target, "allowed": sorted(TRANSITIONS.get(current, ()))}
        )


def required_role(current: str, target: str) -> str:
    """The minimum role for a (validated) transition."""
    return ROLE_FOR_TRANSITION.get((current, target), "officer")


def role_allows(role: str, required: str) -> bool:
    """Roles are ordered: officer ⊇ planner ⊇ viewer."""
    return ROLE_RANK.get(role, -1) >= ROLE_RANK.get(required, 99)
