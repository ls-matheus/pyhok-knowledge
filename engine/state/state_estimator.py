from __future__ import annotations

from math import exp, sqrt
from typing import Iterable, Sequence


DIMENSIONS = (
    "focus",
    "stress",
    "autonomy",
    "fatigue",
)


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + exp(-value))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def fuse_state(
    contributions: Iterable[
        tuple[float, Sequence[float]]
    ],
) -> tuple[dict[str, float], float]:

    raw = [0.0, 0.0, 0.0, 0.0]
    confidence_terms = []

    for effective_evidence, weights in contributions:
        if len(weights) != 4:
            raise ValueError("weights must contain four dimensions")

        if not 0.0 <= effective_evidence <= 1.0:
            raise ValueError("invalid evidence")

        for index in range(4):
            raw[index] += effective_evidence * weights[index]

        confidence_terms.append(effective_evidence)

    z = [
        _sigmoid(value)
        for value in raw
    ]

    confidence = 1.0

    for evidence in confidence_terms:
        confidence *= (1.0 - evidence)

    confidence = 1.0 - confidence

    state = dict(zip(DIMENSIONS, z))

    return state, _clamp(confidence, 0.0, 1.0)


def project_to_b3(
    state: dict[str, float],
    confidence: float,
) -> tuple[float, float, float]:

    vector = (
        state["focus"] - 0.5,
        state["stress"] - 0.5,
        state["fatigue"] - 0.5,
    )

    # Autonomia entra como compensação do eixo de magnitude.
    vector = (
        vector[0] + 0.25 * (state["autonomy"] - 0.5),
        vector[1],
        vector[2],
    )

    norm = sqrt(
        sum(component * component for component in vector)
    )

    if norm <= 1e-12:
        return (0.0, 0.0, 0.0)

    scale = confidence / max(1.0, norm)

    projected = tuple(
        component * scale
        for component in vector
    )

    return tuple(
        _clamp(component, -1.0, 1.0)
        for component in projected
    )


def uncertainty(confidence: float) -> float:
    return 1.0 - confidence
