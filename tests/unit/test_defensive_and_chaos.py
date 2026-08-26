from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scheduler.preflight import (
    check_python_runtime,
    check_dependencies,
    check_critical_paths,
    check_git_workspace_hygiene,
    run_preflight,
)
from scheduler.state import (
    load_status,
    save_status,
    is_circuit_open,
    reset_circuit_breaker,
    is_auto_merge_enabled,
    record_failure,
    record_blocked,
    DEFAULT_STATUS,
)
from scheduler.orchestrator import EvolutionOrchestrator
from evolution.ledger import read_ledger_events, compute_sha256


# ----------------------------------------------------------------------
# 1. Preflight Validation Tests
# ----------------------------------------------------------------------

def test_preflight_python_runtime_and_deps():
    py_ok, _ = check_python_runtime()
    assert py_ok is True
    deps_ok, missing = check_dependencies()
    assert deps_ok is True
    assert missing == []


def test_preflight_detects_missing_critical_file(tmp_path):
    # Empty dir missing all critical files
    paths_ok, missing = check_critical_paths(root=tmp_path)
    assert paths_ok is False
    assert len(missing) > 0
    assert any("question.schema.json" in m for m in missing)


def test_preflight_critical_paths_pass_on_real_repo():
    paths_ok, missing = check_critical_paths(root=ROOT)
    assert paths_ok is True, f"Missing critical paths: {missing}"


# ----------------------------------------------------------------------
# 2. Circuit Breaker Tests
# ----------------------------------------------------------------------

def test_circuit_breaker_tripping_and_reset(tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    import scheduler.state as state_mod
    monkeypatch.setattr(state_mod, "STATUS_FILE", status_file)

    # Initially closed
    is_open, _ = is_circuit_open(status_file)
    assert is_open is False

    # Failure 1
    record_failure("error 1", max_failures=3, status_file=status_file)
    assert is_circuit_open(status_file)[0] is False

    # Failure 2
    record_failure("error 2", max_failures=3, status_file=status_file)
    assert is_circuit_open(status_file)[0] is False

    # Failure 3 -> Trips circuit breaker
    state = record_failure("error 3", max_failures=3, status_file=status_file)
    assert state["status"] == "CIRCUIT_OPEN"
    is_open, reason = is_circuit_open(status_file)
    assert is_open is True
    assert "consecutive failures" in reason

    # Manual reset
    reset_state = reset_circuit_breaker(status_file)
    assert reset_state["status"] == "IDLE"
    assert reset_state["consecutive_failures"] == 0
    assert is_circuit_open(status_file)[0] is False


def test_orchestrator_blocks_when_circuit_is_open(tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    import scheduler.state as state_mod
    monkeypatch.setattr(state_mod, "STATUS_FILE", status_file)
    save_status({
        "status": "CIRCUIT_OPEN",
        "consecutive_failures": 3,
        "circuit_breaker": {"is_open": True, "trip_reason": "test_failure_trip"}
    }, status_file=status_file)

    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps({
        "scheduler": {"enabled": True, "timezone": "America/Sao_Paulo", "start": "00:00", "end": "23:59"}
    }))

    orch = EvolutionOrchestrator(policy_path=policy_file, skip_git=True, skip_preflight=True)
    res = orch.execute_cycle()
    assert res["status"] == "CIRCUIT_OPEN"
    assert "test_failure_trip" in res["reason"]


# ----------------------------------------------------------------------
# 3. Kill Switch & Auto-Merge Tests
# ----------------------------------------------------------------------

def test_auto_merge_kill_switch(monkeypatch):
    # Default is disabled (Shadow Mode)
    monkeypatch.delenv("AUTONOMOUS_MERGE_ENABLED", raising=False)
    assert is_auto_merge_enabled() is False

    # Explicitly enabled
    monkeypatch.setenv("AUTONOMOUS_MERGE_ENABLED", "true")
    assert is_auto_merge_enabled() is True

    # Explicitly disabled
    monkeypatch.setenv("AUTONOMOUS_MERGE_ENABLED", "false")
    assert is_auto_merge_enabled() is False


# ----------------------------------------------------------------------
# 4. Chaos & Defensive Failure Recovery Tests
# ----------------------------------------------------------------------

def test_chaos_llm_api_failure_handled_gracefully(tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    import scheduler.state as state_mod
    monkeypatch.setattr(state_mod, "STATUS_FILE", status_file)

    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps({
        "scheduler": {"enabled": True, "timezone": "America/Sao_Paulo", "start": "00:00", "end": "23:59"}
    }))

    # Mock runner that simulates LLM API network error on run_audit
    def mock_failing_runner(cmd):
        if "run_audit.py" in str(cmd):
            return 1, "", "google.genai.errors.APIError: 503 Service Unavailable"
        return 0, "OK", ""

    orch = EvolutionOrchestrator(
        policy_path=policy_file,
        skip_git=True,
        skip_preflight=True,
        force_window=True,
        runner_fn=mock_failing_runner
    )
    res = orch.execute_cycle()
    assert res["status"] == "FAILED"
    assert "503 Service Unavailable" in res["error"]

    status = load_status(status_file)
    assert status["status"] == "FAILED"
    assert "503" in status["last_error"]


def test_chaos_quality_gate_failure_aborts_cycle(tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    proposal_file = tmp_path / "proposal.json"
    proposal_file.write_text(json.dumps({
        "status": "PROPOSAL_READY",
        "proposal": {
            "proposal_id": "prop_test_gate_fail",
            "opportunity_id": "opp_test",
            "confidence": 0.90,
            "novelty_score": 0.85,
            "coverage_gain": 0.20,
            "question": {
                "id": "q_test_gate_fail",
                "hypothesis": "Valid hypothesis regarding attentional focus decay, controlling for dpi scaling and sensor noise.",
                "required_signals": ["sig_test_pointer_velocity"],
                "evaluation_trigger": {
                    "logical_operator": "AND",
                    "rules": [
                        {"signal_id": "sig_test_pointer_velocity", "operator": ">", "threshold": 0.5, "window_ms": 100}
                    ]
                },
                "evaluation_model": {
                    "method_id": "method_rolling_mean",
                    "version": "1.0.0",
                    "parameters": {}
                },
                "evidence_model": {
                    "base_strength": 0.8,
                    "decay_rate_per_sec": 0.05
                },
                "cortex_weights": {
                    "focus": 0.5,
                    "stress": -0.2,
                    "autonomy": 0.3,
                    "fatigue": -0.1
                }
            }
        }
    }))

    import scheduler.state as state_mod
    monkeypatch.setattr(state_mod, "STATUS_FILE", status_file)
    import scheduler.orchestrator as orch_mod
    monkeypatch.setattr(orch_mod, "PROPOSAL_OUTPUT_FILE", proposal_file)

    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps({
        "scheduler": {"enabled": True, "timezone": "America/Sao_Paulo", "start": "00:00", "end": "23:59"}
    }))

    # Mock runner where validate_dataset fails quality gate
    def mock_gate_failing_runner(cmd):
        if "validate_dataset.py" in str(cmd):
            return 1, "Schema mismatch error", "Schema mismatch"
        return 0, "OK", ""

    orch = EvolutionOrchestrator(
        policy_path=policy_file,
        quarantine_file=tmp_path / "rejected_claims.jsonl",
        skip_git=True,
        skip_preflight=True,
        force_window=True,
        runner_fn=mock_gate_failing_runner
    )
    res = orch.execute_cycle()
    assert res["status"] == "FAILED"
    assert "Quality gates failed" in res["error"]


def test_terminal_no_silent_mutation_guard_detects_dirty_main(tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    proposal_file = tmp_path / "proposal.json"
    proposal_file.write_text(json.dumps({
        "status": "PROPOSAL_READY",
        "proposal": {
            "proposal_id": "prop_test_mutation",
            "opportunity_id": "opp_test",
            "confidence": 0.90,
            "novelty_score": 0.85,
            "coverage_gain": 0.20,
            "question": {
                "id": "q_test_mutation",
                "hypothesis": "Hypothesis about motor activation and focus stability, controlling for dpi scaling and sensor noise.",
                "required_signals": ["sig_test_pointer_velocity"],
                "evaluation_trigger": {
                    "logical_operator": "AND",
                    "rules": [
                        {"signal_id": "sig_test_pointer_velocity", "operator": ">", "threshold": 0.5, "window_ms": 100}
                    ]
                },
                "evaluation_model": {
                    "method_id": "method_rolling_mean",
                    "version": "1.0.0",
                    "parameters": {}
                },
                "evidence_model": {
                    "base_strength": 0.8,
                    "decay_rate_per_sec": 0.05
                },
                "cortex_weights": {
                    "focus": 0.5,
                    "stress": -0.2,
                    "autonomy": 0.3,
                    "fatigue": -0.1
                }
            }
        }
    }))

    import scheduler.state as state_mod
    monkeypatch.setattr(state_mod, "STATUS_FILE", status_file)
    import scheduler.orchestrator as orch_mod
    monkeypatch.setattr(orch_mod, "PROPOSAL_OUTPUT_FILE", proposal_file)

    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps({
        "scheduler": {"enabled": True, "timezone": "America/Sao_Paulo", "start": "00:00", "end": "23:59"}
    }))

    # Mock runner that simulates git checkout main and dirty data/ status
    def mock_dirty_main_runner(cmd):
        if "diff" in cmd and "--cached" in cmd:
            return 1, "staged changes present", ""
        if "status" in cmd and "data/" in cmd:
            return 0, " M data/questions/q_corrupted.json\n", ""
        if "rev-parse" in cmd:
            return 0, "main_sha_123\n", ""
        return 0, "OK", ""

    orch = EvolutionOrchestrator(
        policy_path=policy_file,
        ledger_path=tmp_path / "ledger.jsonl",
        manifests_dir=tmp_path / "manifests",
        evaluations_path=tmp_path / "post_evaluations.jsonl",
        quarantine_file=tmp_path / "rejected_claims.jsonl",
        skip_git=False,
        skip_preflight=True,
        force_window=True,
        runner_fn=mock_dirty_main_runner
    )
    res = orch.execute_cycle()
    assert res["status"] == "FAILED"
    assert "TERMINAL_MUTATION_DETECTED" in res["error"]
