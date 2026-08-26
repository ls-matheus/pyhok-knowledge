from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE_FILE = ROOT / "evolution/baseline.json"
LEDGER_FILE = ROOT / "evolution/ledger.jsonl"
STATUS_FILE = ROOT / "scheduler/status.json"

from evolution.ledger import read_ledger_events, verify_ledger_integrity, hash_knowledge_state
from evolution.baseline import load_baseline, capture_baseline
from evolution.meta_metrics import (
    gate_precision,
    gate_recall,
    mean_absolute_error,
    regression_rates,
    calibration_curve,
)


def generate_shadow_summary_dict(
    ledger_path: Path = LEDGER_FILE,
    baseline_path: Path = BASELINE_FILE,
    status_path: Path = STATUS_FILE,
) -> dict[str, Any]:
    """
    Generates a structured dictionary comparing current state against Baseline N=0 and computing meta-metrics.
    """
    baseline = load_baseline(baseline_path)
    events = read_ledger_events(ledger_path)
    is_valid_ledger, ledger_errors = verify_ledger_integrity(ledger_path)

    # Status & Circuit Breaker info
    status_data = {}
    if status_path.exists():
        try:
            status_data = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    circuit_breaker_events = 1 if status_data.get("circuit_breaker", {}).get("is_open") else 0
    circuit_breaker_events = status_data.get("stats", {}).get("circuit_breaker_trips", 0)
    if circuit_breaker_events == 0 and status_data.get("circuit_breaker", {}).get("is_open"):
        circuit_breaker_events = 1

    total_cycles = len(events)
    predicted_improvements = sum(
        1 for e in events
        if e.get("gate_verdict", {}).get("classification") == "PREDICTED_IMPROVEMENT"
    )

    evaluated_events = [e for e in events if e.get("post_evaluation")]
    actually_improved = sum(
        1 for e in evaluated_events
        if e.get("post_evaluation", {}).get("actually_improved")
    )

    precision = gate_precision(events) if evaluated_events else 0.0
    recall = gate_recall(events) if evaluated_events else 0.0

    novelty_pairs = []
    coverage_pairs = []
    for e in evaluated_events:
        preds = e.get("predictions", {})
        obs = e.get("post_evaluation", {}).get("observed", {})
        if "novelty_score" in preds and "novelty" in obs:
            novelty_pairs.append((preds["novelty_score"], obs["novelty"]))
        if "coverage_gain" in preds and "coverage_gain" in obs:
            coverage_pairs.append((preds["coverage_gain"], obs["coverage_gain"]))

    novelty_mae = mean_absolute_error(novelty_pairs)
    coverage_mae = mean_absolute_error(coverage_pairs)
    reg_rates = regression_rates(events)

    # Current snapshot comparison
    current_snapshot = capture_baseline()
    baseline_coverage = baseline.get("coverage", 0.10)
    current_coverage = current_snapshot.get("coverage", 0.10)
    coverage_delta = round(current_coverage - baseline_coverage, 4)

    baseline_redundancy = baseline.get("redundancy", 0.0)
    current_redundancy = current_snapshot.get("redundancy", 0.0)

    return {
        "cycles_total": total_cycles,
        "predicted_improvements": predicted_improvements,
        "actually_improved": actually_improved,
        "gate_precision": round(precision * 100, 2),
        "gate_recall": round(recall * 100, 2),
        "novelty_mae": round(novelty_mae, 4),
        "coverage_mae": round(coverage_mae, 4),
        "regression_rate": round(reg_rates.get("overall_regression_rate", 0.0) * 100, 2),
        "baseline_coverage": baseline_coverage,
        "current_coverage": current_coverage,
        "coverage_delta": coverage_delta,
        "baseline_redundancy": baseline_redundancy,
        "current_redundancy": current_redundancy,
        "circuit_breaker_events": circuit_breaker_events,
        "ledger_integrity": "PASS" if is_valid_ledger else "FAIL",
        "ledger_errors": ledger_errors
    }


def generate_shadow_report(
    ledger_path: Path = LEDGER_FILE,
    baseline_path: Path = BASELINE_FILE,
    status_path: Path = STATUS_FILE,
) -> str:
    """
    Formats the formal longitudinal Shadow Evolution Report string.
    """
    summary = generate_shadow_summary_dict(ledger_path, baseline_path, status_path)
    sign = "+" if summary["coverage_delta"] >= 0 else ""

    report = (
        "PYHOK — SHADOW EVOLUTION REPORT\n"
        "===============================\n\n"
        f"Cycles:\n{summary['cycles_total']}\n\n"
        f"Predicted Improvements:\n{summary['predicted_improvements']}\n\n"
        f"Actually Improved:\n{summary['actually_improved']}\n\n"
        f"Gate Precision:\n{summary['gate_precision']}%\n\n"
        f"Gate Recall:\n{summary['gate_recall']}%\n\n"
        f"Novelty MAE:\n{summary['novelty_mae']:.4f}\n\n"
        f"Coverage MAE:\n{summary['coverage_mae']:.4f}\n\n"
        f"Regression Rate:\n{summary['regression_rate']}%\n\n"
        f"Baseline Coverage:\n{summary['baseline_coverage']:.2f}\n\n"
        f"Final Coverage:\n{summary['current_coverage']:.2f}\n\n"
        f"Coverage Δ:\n{sign}{summary['coverage_delta']:.2f}\n\n"
        f"Baseline Redundancy:\n{summary['baseline_redundancy']:.2f}\n\n"
        f"Final Redundancy:\n{summary['current_redundancy']:.2f}\n\n"
        f"Circuit Breaker Events:\n{summary['circuit_breaker_events']}\n\n"
        f"Ledger Integrity:\n{summary['ledger_integrity']}\n"
    )
    return report


def main() -> int:
    report = generate_shadow_report()
    print(report)
    return 0


if __name__ == "__main__":
    main()
