from __future__ import annotations

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.post_evaluator import (
    evaluate_proposal_impact,
    attach_post_evaluation,
)
from evolution.meta_metrics import (
    prediction_error,
    mean_absolute_error,
    gate_precision,
    gate_recall,
    calibration_curve,
    regression_rates,
    generate_meta_metrics_report,
)


# ----------------------------------------------------------------------
# 1. Post Evaluator Unit Tests
# ----------------------------------------------------------------------

def test_evaluate_proposal_impact_improvement():
    state_before = {
        "questions": [{"id": "q_001", "required_signals": ["sig_01"]}],
        "signals": [{"id": "sig_01"}, {"id": "sig_02"}],
        "relations": []
    }
    proposal = {
        "proposal_id": "prop_002",
        "question": {"id": "q_002", "required_signals": ["sig_02"]}
    }
    state_after = {
        "questions": [{"id": "q_001", "required_signals": ["sig_01"]}, {"id": "q_002", "required_signals": ["sig_02"]}],
        "signals": [{"id": "sig_01"}, {"id": "sig_02"}],
        "relations": []
    }

    eval_result = evaluate_proposal_impact(state_before, proposal, state_after)
    assert eval_result["actually_improved"] is True
    assert eval_result["observed"]["coverage_gain"] > 0.0
    assert eval_result["observed"]["redundancy"] == 0.0
    assert eval_result["observed"]["regression"] is False


def test_evaluate_proposal_impact_redundancy():
    state_before = {
        "questions": [{"id": "q_001", "required_signals": ["sig_01"]}],
        "signals": [{"id": "sig_01"}],
        "relations": []
    }
    # Duplicate existing signals and behavior
    proposal = {
        "proposal_id": "prop_dup",
        "question": {"id": "q_dup", "required_signals": ["sig_01"]}
    }
    state_after = {
        "questions": [{"id": "q_001", "required_signals": ["sig_01"]}, {"id": "q_dup", "required_signals": ["sig_01"]}],
        "signals": [{"id": "sig_01"}],
        "relations": []
    }

    eval_result = evaluate_proposal_impact(state_before, proposal, state_after, max_redundancy_threshold=0.0)
    assert eval_result["actually_improved"] is False
    assert eval_result["observed"]["redundancy"] > 0.0
    assert eval_result["observed"]["redundancy"] == 1.0  # Exact duplicate signal set


def test_evaluate_proposal_impact_jaccard_similarity():
    state_before = {
        "questions": [{"id": "q_001", "required_signals": ["sig_01", "sig_02"]}],
        "signals": [{"id": "sig_01"}, {"id": "sig_02"}, {"id": "sig_03"}],
        "relations": []
    }
    # Jaccard: {1,2} vs {1,2,3} -> 2/3 = 0.6667
    proposal = {
        "proposal_id": "prop_partial_overlap",
        "question": {"id": "q_partial", "required_signals": ["sig_01", "sig_02", "sig_03"]}
    }
    state_after = {
        "questions": [{"id": "q_001", "required_signals": ["sig_01", "sig_02"]}, {"id": "q_partial", "required_signals": ["sig_01", "sig_02", "sig_03"]}],
        "signals": [{"id": "sig_01"}, {"id": "sig_02"}, {"id": "sig_03"}],
        "relations": []
    }

    eval_result = evaluate_proposal_impact(state_before, proposal, state_after)
    assert eval_result["observed"]["redundancy"] == pytest.approx(0.6667, abs=1e-3)
    assert eval_result["observed"]["signal_coverage_delta"] == pytest.approx(1 / 3, abs=1e-3)
# ----------------------------------------------------------------------
# 2. Meta-Metrics Engine Unit Tests
# ----------------------------------------------------------------------

def test_prediction_error_and_mae():
    assert prediction_error(0.85, 0.79) == pytest.approx(0.06, abs=1e-4)
    assert prediction_error(0.70, 0.70) == pytest.approx(0.0, abs=1e-4)

    pairs = [(0.85, 0.79), (0.90, 0.80), (0.75, 0.75)]
    # (0.06 + 0.10 + 0.00) / 3 = 0.05333...
    assert mean_absolute_error(pairs) == pytest.approx(0.05333, abs=1e-4)


def test_precision_and_recall_calculation():
    # Sample evaluation history: 4 records
    history = [
        # TP: predicted IMPROVEMENT, actually improved
        {"gate_verdict": {"classification": "PREDICTED_IMPROVEMENT"}, "post_evaluation": {"actually_improved": True}},
        # FP: predicted IMPROVEMENT, actually not improved
        {"gate_verdict": {"classification": "PREDICTED_IMPROVEMENT"}, "post_evaluation": {"actually_improved": False}},
        # TN: predicted NEUTRAL/REJECTED, actually not improved
        {"gate_verdict": {"classification": "PREDICTED_NEUTRAL"}, "post_evaluation": {"actually_improved": False}},
        # FN: predicted NEUTRAL/REJECTED, actually improved
        {"gate_verdict": {"classification": "PREDICTED_NEUTRAL"}, "post_evaluation": {"actually_improved": True}},
    ]

    # Precision: TP / (TP + FP) = 1 / (1 + 1) = 0.50
    assert gate_precision(history) == pytest.approx(0.50)

    # Recall: TP / (TP + FN) = 1 / (1 + 1) = 0.50
    assert gate_recall(history) == pytest.approx(0.50)


def test_calibration_curve():
    history = [
        {"predictions": {"confidence": 0.85}, "post_evaluation": {"actually_improved": True}},
        {"predictions": {"confidence": 0.88}, "post_evaluation": {"actually_improved": True}},
        {"predictions": {"confidence": 0.65}, "post_evaluation": {"actually_improved": False}},
        {"predictions": {"confidence": 0.62}, "post_evaluation": {"actually_improved": True}},
    ]
    buckets = [(0.60, 0.70), (0.80, 0.90)]
    curve = calibration_curve(history, buckets=buckets)

    assert len(curve) == 2
    # Bucket [0.60, 0.70): 2 samples, 1 true -> 0.50
    assert curve[0]["bucket"] == "0.60-0.70"
    assert curve[0]["count"] == 2
    assert curve[0]["accuracy"] == pytest.approx(0.50)

    # Bucket [0.80, 0.90): 2 samples, 2 true -> 1.00
    assert curve[1]["bucket"] == "0.80-0.90"
    assert curve[1]["count"] == 2
    assert curve[1]["accuracy"] == pytest.approx(1.00)


def test_regression_rates_and_comprehensive_report():
    history = [
        {
            "cycle_id": "cycle_01",
            "predictions": {"novelty_score": 0.85, "coverage_gain": 0.20, "confidence": 0.90},
            "gate_verdict": {"classification": "PREDICTED_IMPROVEMENT"},
            "post_evaluation": {
                "observed": {"novelty": 0.80, "coverage_gain": 0.18, "redundancy": 0.0, "regression": False, "regression_type": None},
                "actually_improved": True
            }
        },
        {
            "cycle_id": "cycle_02",
            "predictions": {"novelty_score": 0.75, "coverage_gain": 0.10, "confidence": 0.80},
            "gate_verdict": {"classification": "PREDICTED_IMPROVEMENT"},
            "post_evaluation": {
                "observed": {"novelty": 0.70, "coverage_gain": 0.0, "redundancy": 0.05, "regression": True, "regression_type": "structural"},
                "actually_improved": False
            }
        }
    ]

    rates = regression_rates(history)
    assert rates["overall_regression_rate"] == pytest.approx(0.50)
    assert rates["structural_regression_rate"] == pytest.approx(0.50)

    report = generate_meta_metrics_report(history)
    assert report["total_evaluated_cycles"] == 2
    assert report["gate_precision"] == pytest.approx(0.50)
    assert "mae_novelty" in report
    assert "mae_coverage" in report
