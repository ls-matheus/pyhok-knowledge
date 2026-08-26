from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.baseline import capture_baseline, save_baseline, load_baseline
from evolution.shadow_report import generate_shadow_summary_dict, generate_shadow_report
from evolution.ledger import append_ledger_event


def test_baseline_capture_and_load(tmp_path):
    baseline_file = tmp_path / "baseline.json"
    data = capture_baseline(root=ROOT)

    assert data["baseline_id"] == "baseline_n0"
    assert data["counts"]["questions"] >= 1
    assert data["counts"]["signals"] >= 1
    assert data["counts"]["total_domains"] == 10
    assert data["coverage"] == 0.10
    assert data["redundancy"] == 0.0
    assert "attention_disruption" in data["known_gaps"]

    save_baseline(data, baseline_path=baseline_file)
    loaded = load_baseline(baseline_path=baseline_file)
    assert loaded["baseline_id"] == "baseline_n0"
    assert loaded["state_hash"] == data["state_hash"]


def test_shadow_report_generation(tmp_path):
    baseline_file = tmp_path / "baseline.json"
    ledger_file = tmp_path / "ledger.jsonl"
    status_file = tmp_path / "status.json"

    # Save baseline
    b_data = capture_baseline(root=ROOT)
    save_baseline(b_data, baseline_path=baseline_file)

    # Save status
    status_file.write_text(json.dumps({"circuit_breaker": {"is_open": False}}), encoding="utf-8")

    # Add a mock ledger event with post_evaluation
    event_1 = {
        "cycle_id": "cycle_20260826_230001",
        "timestamp": "2026-08-26T23:00:01Z",
        "previous_event_hash": None,
        "initial_state_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
        "proposal_hash": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
        "resulting_state_hash": "sha256:3333333333333333333333333333333333333333333333333333333333333333",
        "proposal_id": "prop_opp_test_01",
        "predictions": {
            "novelty_score": 0.85,
            "coverage_gain": 0.20,
            "confidence": 0.90
        },
        "gate_verdict": {
            "valid": True,
            "safe": True,
            "classification": "PREDICTED_IMPROVEMENT"
        },
        "action_taken": "SHADOW_RECORDED",
        "post_evaluation": {
            "observed": {
                "novelty": 0.80,
                "coverage_gain": 0.18,
                "redundancy": 0.0,
                "regression": False,
                "regression_type": None
            },
            "actually_improved": True,
            "evaluation_timestamp": "2026-08-26T23:30:00Z"
        }
    }
    append_ledger_event(event_1, ledger_path=ledger_file)

    summary = generate_shadow_summary_dict(ledger_path=ledger_file, baseline_path=baseline_file, status_path=status_file)
    assert summary["cycles_total"] == 1
    assert summary["predicted_improvements"] == 1
    assert summary["actually_improved"] == 1
    assert summary["gate_precision"] == 100.0
    assert summary["gate_recall"] == 100.0
    assert summary["novelty_mae"] == pytest.approx(0.05, abs=1e-4)
    assert summary["coverage_mae"] == pytest.approx(0.02, abs=1e-4)
    assert summary["ledger_integrity"] == "PASS"

    report_str = generate_shadow_report(ledger_path=ledger_file, baseline_path=baseline_file, status_path=status_file)
    assert "PYHOK — SHADOW EVOLUTION REPORT" in report_str
    assert "Cycles:\n1" in report_str
    assert "Gate Precision:\n100.0%" in report_str
    assert "Ledger Integrity:\nPASS" in report_str
