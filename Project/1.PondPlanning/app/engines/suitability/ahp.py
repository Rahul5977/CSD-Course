"""Analytic Hierarchy Process (Saaty 1980): criterion weights with a consistency check.

A pairwise comparison matrix ``A`` (``a_ij`` = how much more important
criterion i is than j, on Saaty's 1-9 scale, ``a_ji = 1/a_ij``) yields the
weights as its **principal eigenvector**. Judgements are never perfectly
transitive, so the **consistency ratio** ``CR = CI / RI`` with
``CI = (λ_max - n) / (n - 1)`` and Saaty's random index ``RI`` is computed
and returned; ``CR < 0.10`` is the accepted threshold. The matrix and the CR
go in the response so the ranking is checkable, not asserted.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.domain.errors import ValidationError

#: Saaty's random consistency index for n = 1..10.
RANDOM_INDEX: tuple[float, ...] = (0.0, 0.0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49)

#: Default judgements for the siting criteria (row dominates column).
#: upstream area vs flatness 2, vs wetness 3, vs impoundment 1; flatness vs
#: wetness 2, vs impoundment 1/2; wetness vs impoundment 1/3.
DEFAULT_CRITERIA: tuple[str, ...] = ("upstream_area", "flatness", "wetness", "impoundment")
DEFAULT_MATRIX: tuple[tuple[float, ...], ...] = (
    (1.0, 2.0, 3.0, 1.0),
    (1 / 2, 1.0, 2.0, 1 / 2),
    (1 / 3, 1 / 2, 1.0, 1 / 3),
    (1.0, 2.0, 3.0, 1.0),
)


@dataclass(frozen=True, slots=True)
class AHPResult:
    """Weights and the consistency evidence."""

    criteria: tuple[str, ...]
    weights: dict[str, float]
    lambda_max: float
    consistency_index: float
    consistency_ratio: float
    acceptable: bool
    matrix: list[list[float]]


def ahp_weights(
    matrix: NDArray[np.float64] | tuple[tuple[float, ...], ...],
    criteria: tuple[str, ...] = DEFAULT_CRITERIA,
    *,
    threshold: float = 0.10,
) -> AHPResult:
    """Principal-eigenvector weights and Saaty's consistency ratio.

    Raises:
        ValidationError: If the matrix is not square, positive and reciprocal.
    """
    a = np.asarray(matrix, dtype=np.float64)
    n = a.shape[0]
    if a.ndim != 2 or a.shape[1] != n or n != len(criteria):
        msg = "AHP matrix must be square and match the criteria"
        raise ValidationError(msg, {"shape": list(a.shape), "criteria": list(criteria)})
    if (a <= 0).any() or not np.allclose(a * a.T, 1.0, rtol=1e-6):
        msg = "AHP matrix must be positive and reciprocal (a_ji = 1 / a_ij)"
        raise ValidationError(msg)
    values, vectors = np.linalg.eig(a)
    k = int(np.argmax(values.real))
    lam = float(values[k].real)
    w = np.abs(vectors[:, k].real)
    w = w / w.sum()
    ci = (lam - n) / (n - 1) if n > 1 else 0.0
    ri = RANDOM_INDEX[n - 1] if n <= len(RANDOM_INDEX) else 1.49
    cr = ci / ri if ri > 0 else 0.0
    return AHPResult(
        criteria=tuple(criteria),
        weights={c: float(x) for c, x in zip(criteria, w, strict=True)},
        lambda_max=lam,
        consistency_index=float(ci),
        consistency_ratio=float(cr),
        acceptable=bool(cr < threshold),
        matrix=a.round(4).tolist(),
    )
