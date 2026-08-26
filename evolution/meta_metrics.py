from __future__ import annotations

from typing import Any


def prediction_error(predicted: float, observed: float) -> float:
    """
    Computes absolute error between an agent's self-assessed prediction and the empirical observation.
    """
    return abs(float(predicted) - float(observed))


def mean_absolute_error(pairs: list[tuple[float, float]]) -> float:
    """
    Computes Mean Absolute Error across a list of (predicted, observed) metric pairs.
    """
    if not pairs:
        return 0.0
    return sum(abs(p - o) for p, o in pairs) / len(pairs)


def gate_precision(history: list[dict[str, Any]]) -> float:
    """
    Computes the precision of the Improvement Gate: TP / (TP + FP).
    Measures: 'When the gate predicted an improvement, how often was it genuinely an improvement?'
    """
    tp = 0
    fp = 0
    for record in history:
        verdict = record.get("gate_verdict", {}).get("classification")
        post = record.get("post_evaluation", {})
        if not post:
            continue
        actually_improved = post.get("actually_improved", False)

        if verdict == "PREDICTED_IMPROVEMENT":
            if actually_improved:
                tp += 1
            else:
                fp += 1

    total_positive_predictions = tp + fp
    if total_positive_predictions == 0:
        return 0.0
    return tp / total_positive_predictions


def gate_recall(history: list[dict[str, Any]]) -> float:
    """
    Computes the recall of the Improvement Gate: TP / (TP + FN).
    Measures: 'Out of all genuine improvements, how many did the gate successfully predict?'
    """
    tp = 0
    fn = 0
    for record in history:
        verdict = record.get("gate_verdict", {}).get("classification")
        post = record.get("post_evaluation", {})
        if not post:
            continue
        actually_improved = post.get("actually_improved", False)

        if actually_improved:
            if verdict == "PREDICTED_IMPROVEMENT":
                tp += 1
            else:
                fn += 1

    total_actual_improvements = tp + fn
    if total_actual_improvements == 0:
        return 0.0
    return tp / total_actual_improvements


def calibration_curve(
    history: list[dict[str, Any]],
    buckets: list[tuple[float, float]] | None = None
) -> list[dict[str, Any]]:
    """
    Computes empirical accuracy across confidence interval buckets to measure calibration quality.
    """
    if buckets is None:
        buckets = [
            (0.50, 0.60),
            (0.60, 0.70),
            (0.70, 0.80),
            (0.80, 0.90),
            (0.90, 1.00)
        ]

    curve: list[dict[str, Any]] = []

    for low, high in buckets:
        matching = []
        for r in history:
            conf = r.get("predictions", {}).get("confidence", 0.0)
            post = r.get("post_evaluation")
            if post is None:
                continue
            if high == 1.00:
                if low <= conf <= high:
                    matching.append(post.get("actually_improved", False))
            else:
                if low <= conf < high:
                    matching.append(post.get("actually_improved", False))

        count = len(matching)
        accuracy = (sum(1 for x in matching if x) / count) if count > 0 else 0.0
        curve.append({
            "bucket": f"{low:.2f}-{high:.2f}",
            "count": count,
            "accuracy": round(accuracy, 4)
        })

    return curve


def regression_rates(history: list[dict[str, Any]]) -> dict[str, float]:
    """
    Calculates overall and category-specific regression rates.
    """
    total = 0
    structural_reg = 0
    semantic_reg = 0
    runtime_reg = 0

    for r in history:
        post = r.get("post_evaluation")
        if not post:
            continue
        obs = post.get("observed", {})
        total += 1
        if obs.get("regression", False):
            reg_type = obs.get("regression_type")
            if reg_type == "structural" or reg_type == "unexpected_deletion":
                structural_reg += 1
            elif reg_type == "semantic":
                semantic_reg += 1
            elif reg_type == "runtime":
                runtime_reg += 1
            else:
                structural_reg += 1

    if total == 0:
        return {
            "overall_regression_rate": 0.0,
            "structural_regression_rate": 0.0,
            "semantic_regression_rate": 0.0,
            "runtime_regression_rate": 0.0
        }

    return {
        "overall_regression_rate": (structural_reg + semantic_reg + runtime_reg) / total,
        "structural_regression_rate": structural_reg / total,
        "semantic_regression_rate": semantic_reg / total,
        "runtime_regression_rate": runtime_reg / total
    }


def generate_meta_metrics_report(history: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Generates a full empirical meta-evaluation report across all recorded evolution cycles.
    """
    novelty_pairs: list[tuple[float, float]] = []
    coverage_pairs: list[tuple[float, float]] = []

    for r in history:
        preds = r.get("predictions", {})
        post = r.get("post_evaluation", {})
        if not post:
            continue
        obs = post.get("observed", {})
        if "novelty_score" in preds and "novelty" in obs:
            novelty_pairs.append((preds["novelty_score"], obs["novelty"]))
        if "coverage_gain" in preds and "coverage_gain" in obs:
            coverage_pairs.append((preds["coverage_gain"], obs["coverage_gain"]))

    precision = gate_precision(history)
    recall = gate_recall(history)
    curve = calibration_curve(history)
    reg_rates = regression_rates(history)

    return {
        "total_evaluated_cycles": len([r for r in history if r.get("post_evaluation")]),
        "gate_precision": round(precision, 4),
        "gate_recall": round(recall, 4),
        "mae_novelty": round(mean_absolute_error(novelty_pairs), 4),
        "mae_coverage": round(mean_absolute_error(coverage_pairs), 4),
        "regression_rates": reg_rates,
        "calibration_curve": curve
    }
