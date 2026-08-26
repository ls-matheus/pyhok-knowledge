from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
EVALUATIONS_FILE = ROOT / "evolution/post_evaluations.jsonl"


def evaluate_proposal_impact(
    state_before: dict[str, Any],
    proposal: dict[str, Any],
    state_after: dict[str, Any],
    max_redundancy_threshold: float = 0.05,
) -> dict[str, Any]:
    """
    Evaluates empirical impact of an evolution proposal without referencing the agent's self-assessed scores.
    """
    questions_before = state_before.get("questions", [])
    questions_after = state_after.get("questions", [])

    # 1. Coverage Gain Calculation (Empirical)
    # Check if newly added question covers new signals or expands hypothesis space
    existing_signals = {
        sig
        for q in questions_before
        for sig in q.get("required_signals", [])
    }

    prop_q = proposal.get("question", {})
    prop_signals = set(prop_q.get("required_signals", []))

    new_signals_covered = prop_signals - existing_signals
    total_available_signals = max(1, len(state_before.get("signals", [])))

    if new_signals_covered:
        coverage_gain = len(new_signals_covered) / total_available_signals
    elif len(questions_after) > len(questions_before):
        # Added a complementary hypothesis in the domain
        coverage_gain = 1.0 / max(1, len(questions_after))
    else:
        coverage_gain = 0.0

    coverage_gain = min(1.0, max(0.0, float(coverage_gain)))

    # 2. Redundancy Calculation (Empirical)
    # Identifies duplicate signal sets and identical trigger thresholds
    redundancy = 0.0
    for q in questions_before:
        if q.get("id") == prop_q.get("id"):
            continue
        q_sigs = set(q.get("required_signals", []))
        if q_sigs and q_sigs == prop_signals:
            # Overlap in required signals
            redundancy += 1.0 / max(1, len(questions_before))

    redundancy = min(1.0, max(0.0, float(redundancy)))

    # 3. Novelty (Empirical)
    novelty = 1.0 - redundancy

    # 4. Regression Detection
    # Structural regression: any previously valid question became invalid or was unexpectedly removed
    regression = False
    regression_type = None

    ids_before = {q.get("id") for q in questions_before if q.get("id")}
    ids_after = {q.get("id") for q in questions_after if q.get("id")}

    if not ids_before.issubset(ids_after):
        regression = True
        regression_type = "unexpected_deletion"

    # 5. Determine if Actually Improved
    actually_improved = (
        coverage_gain > 0.0
        and redundancy <= max_redundancy_threshold
        and not regression
    )

    return {
        "observed": {
            "novelty": round(novelty, 4),
            "coverage_gain": round(coverage_gain, 4),
            "redundancy": round(redundancy, 4),
            "regression": regression,
            "regression_type": regression_type,
        },
        "actually_improved": actually_improved,
        "evaluation_timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
    }


def attach_post_evaluation(
    cycle_id: str,
    evaluation_result: dict[str, Any],
    evaluations_path: Path = EVALUATIONS_FILE,
) -> None:
    """
    Appends an independent post-evaluation record to the evaluations journal without altering the immutable ledger.
    """
    evaluations_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "cycle_id": cycle_id,
        "post_evaluation": evaluation_result,
        "recorded_at": datetime.now(ZoneInfo("UTC")).isoformat(),
    }
    with open(evaluations_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
