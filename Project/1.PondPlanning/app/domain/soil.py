"""Hydrologic soil groups — a domain concept shared by providers and engines."""

from __future__ import annotations

from typing import Literal

HSG = Literal["A", "B", "C", "D"]


def hsg_from_texture(clay_pct: float, sand_pct: float) -> HSG:
    """USDA texture → hydrologic soil group (the rule of thumb TR-55 users apply).

    A: sand-dominated, high infiltration · B: loams · C: clay loams · D: clays.
    """
    if sand_pct >= 70 and clay_pct < 15:
        return "A"
    if clay_pct >= 40:
        return "D"
    if clay_pct >= 27:
        return "C"
    return "B"
