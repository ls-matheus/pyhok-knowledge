from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Sequence


@dataclass(frozen=True)
class BaselineDeviationResult:
    baseline_center: float
    baseline_mad: float
    current_center: float
    robust_deviation: float
    evidence: float
    activated: bool


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def evaluate(
    baseline: Sequence[float],
    current: Sequence[float],
    deviation_threshold: float,
) -> BaselineDeviationResult:

    if not baseline:
        raise ValueError("baseline must not be empty")

    if not current:
        raise ValueError("current must not be empty")

    if deviation_threshold <= 0:
        raise ValueError("deviation_threshold must be > 0")

    baseline_center = median(baseline)
    deviations = [
        abs(value - baseline_center)
        for value in baseline
    ]

    baseline_mad = median(deviations)

    # Evita divisão por zero em uma baseline completamente estável.
    scale = max(baseline_mad, 1e-9)

    current_center = median(current)

    robust_deviation = abs(
        current_center - baseline_center
    ) / scale

    activated = (
        robust_deviation >= deviation_threshold
    )

    if activated:
        evidence = _clamp(
            (robust_deviation - deviation_threshold)
            / deviation_threshold
        )
    else:
        evidence = 0.0

    if not isfinite(evidence):
        raise ValueError("non-finite evidence")

    return BaselineDeviationResult(
        baseline_center=baseline_center,
        baseline_mad=baseline_mad,
        current_center=current_center,
        robust_deviation=robust_deviation,
        evidence=evidence,
        activated=activated,
    )
