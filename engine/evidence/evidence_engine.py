from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceResult:
    evidence: float
    quality: float
    effective_evidence: float


def apply_quality(
    evidence: float,
    quality: float,
) -> EvidenceResult:

    if not 0.0 <= evidence <= 1.0:
        raise ValueError("evidence must be within [0, 1]")

    if not 0.0 <= quality <= 1.0:
        raise ValueError("quality must be within [0, 1]")

    return EvidenceResult(
        evidence=evidence,
        quality=quality,
        effective_evidence=evidence * quality,
    )
