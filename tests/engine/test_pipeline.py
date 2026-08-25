from engine.evidence.baseline_deviation import evaluate
from engine.evidence.evidence_engine import apply_quality
from engine.state.state_estimator import (
    fuse_state,
    project_to_b3,
    uncertainty,
)


def test_baseline_deviation_pipeline():
    baseline = [
        100.0,
        102.0,
        98.0,
        101.0,
        99.0,
    ]

    current = [
        104.0,
        105.0,
        106.0,
    ]

    result = evaluate(
        baseline=baseline,
        current=current,
        deviation_threshold=1.5,
    )

    assert result.activated is True
    assert result.evidence > 0.0

    weighted = apply_quality(
        evidence=result.evidence,
        quality=0.95,
    )

    state, confidence = fuse_state(
        [
            (
                weighted.effective_evidence,
                (-0.2, 0.3, 0.0, 0.3),
            )
        ]
    )

    point = project_to_b3(
        state=state,
        confidence=confidence,
    )

    assert all(
        0.0 <= value <= 1.0
        for value in state.values()
    )

    assert 0.0 <= confidence <= 1.0

    assert 0.0 <= uncertainty(confidence) <= 1.0

    x, y, z = point

    assert -1.0 <= x <= 1.0
    assert -1.0 <= y <= 1.0
    assert -1.0 <= z <= 1.0
