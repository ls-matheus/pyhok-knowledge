from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.baseline import capture_baseline, save_baseline, verify_baseline_integrity
from evolution.manifest import create_cycle_manifest
from evolution.measurement_gate import verify_cycle_manifest_integrity, verify_measurement_integrity
from evolution.ledger import append_ledger_event, compute_sha256


def test_baseline_cryptographic_tamper_detection(tmp_path):
    baseline_file = tmp_path / "baseline.json"
    data = capture_baseline(root=ROOT)
    save_baseline(data, baseline_path=baseline_file)

    # 1. Valid baseline passes
    is_valid, msg = verify_baseline_integrity(baseline_path=baseline_file)
    assert is_valid is True
    assert msg == "BASELINE_VALID"

    # 2. Tampered baseline is detected
    data["coverage"] = 0.99
    # Save without updating the cryptographic hash
    baseline_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    is_valid_tampered, msg_tampered = verify_baseline_integrity(baseline_path=baseline_file)
    assert is_valid_tampered is False
    assert "BASELINE_TAMPERED" in msg_tampered


def test_cycle_manifest_integrity_verification(tmp_path):
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    ledger_file = tmp_path / "ledger.jsonl"

    cycle_id = "cycle_20260826_235959"
    state_before_hash = "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    state_after_hash = "sha256:2222222222222222222222222222222222222222222222222222222222222222"
    proposal_hash = "sha256:3333333333333333333333333333333333333333333333333333333333333333"

    event = {
        "cycle_id": cycle_id,
        "timestamp": "2026-08-26T23:59:59Z",
        "previous_event_hash": None,
        "initial_state_hash": state_before_hash,
        "proposal_hash": proposal_hash,
        "resulting_state_hash": state_after_hash,
        "proposal_id": "prop_test_01",
        "predictions": {"novelty_score": 0.85, "coverage_gain": 0.20, "confidence": 0.90},
        "gate_verdict": {"valid": True, "safe": True, "classification": "PREDICTED_IMPROVEMENT"},
        "action_taken": "SHADOW_RECORDED",
        "post_evaluation": None
    }
    append_ledger_event(event, ledger_path=ledger_file)

    manifest_data = create_cycle_manifest(
        cycle_id=cycle_id,
        main_before_sha="abc1234",
        state_before_hash=state_before_hash,
        state_after_hash=state_after_hash,
        proposal_hash=proposal_hash,
        dataset_counts_before={"questions": 1, "signals": 1, "relations": 0},
        dataset_counts_after={"questions": 2, "signals": 1, "relations": 0},
        predicted_metrics={"novelty_score": 0.85, "coverage_gain": 0.20, "confidence": 0.90},
        observed_metrics={"novelty": 0.80, "coverage_gain": 0.15, "domain_coverage_delta": 0.10, "signal_coverage_delta": 0.0, "redundancy": 0.20},
        gate_verdict={"valid": True, "safe": True, "classification": "PREDICTED_IMPROVEMENT"},
        action_taken="SHADOW_RECORDED",
        timestamp_start="2026-08-26T23:59:50Z",
        manifests_dir=manifests_dir
    )

    # Valid manifest check
    is_valid, errors = verify_cycle_manifest_integrity(manifest_data, ledger_events=[event])
    assert is_valid is True
    assert errors == []

    # Corrupted manifest check (mismatched proposal hash)
    manifest_data_corrupted = dict(manifest_data)
    manifest_data_corrupted["proposal_hash"] = "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    is_valid_corr, errors_corr = verify_cycle_manifest_integrity(manifest_data_corrupted, ledger_events=[event])
    assert is_valid_corr is False
    assert any("proposal_hash does not match" in e for e in errors_corr)
