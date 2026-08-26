from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scheduler.window_guard import is_window_open
from scheduler.state import (
    load_status,
    save_status,
    start_cycle,
    update_phase,
    record_success,
    record_failure,
    record_skip,
    DEFAULT_STATUS,
)
from scheduler.quality_gate import run_quality_gates
from scheduler.orchestrator import EvolutionOrchestrator


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.delenv("MANUAL_OVERRIDE", raising=False)
    status_file = tmp_path / "global_status.json"
    import scheduler.state as state_mod
    monkeypatch.setattr(state_mod, "STATUS_FILE", status_file)
    state_mod.save_status(dict(state_mod.DEFAULT_STATUS), status_file=status_file)


# ----------------------------------------------------------------------
# Pilar 2: Window Guard Unit Tests
# ----------------------------------------------------------------------

@pytest.fixture
def sample_policy() -> dict[str, Any]:
    return {
        "policy_id": "test_policy",
        "scheduler": {
            "enabled": True,
            "timezone": "America/Sao_Paulo",
            "start": "08:00",
            "end": "20:00",
            "tick_minutes": 30
        },
        "limits": {
            "max_consecutive_rejections": 2,
            "minimum_confidence_in_proposal": 0.8
        }
    }


def test_window_guard_inside_window(sample_policy):
    tz = ZoneInfo("America/Sao_Paulo")
    dt = datetime(2026, 8, 26, 14, 30, tzinfo=tz)
    is_open, reason, meta = is_window_open(sample_policy, current_dt=dt)
    assert is_open is True
    assert reason == "within_scheduled_window"


def test_window_guard_before_window(sample_policy):
    tz = ZoneInfo("America/Sao_Paulo")
    dt = datetime(2026, 8, 26, 7, 59, tzinfo=tz)
    is_open, reason, meta = is_window_open(sample_policy, current_dt=dt)
    assert is_open is False
    assert reason == "outside_scheduled_window"


def test_window_guard_after_window(sample_policy):
    tz = ZoneInfo("America/Sao_Paulo")
    dt = datetime(2026, 8, 26, 20, 1, tzinfo=tz)
    is_open, reason, meta = is_window_open(sample_policy, current_dt=dt)
    assert is_open is False
    assert reason == "outside_scheduled_window"


def test_window_guard_exact_boundaries(sample_policy):
    tz = ZoneInfo("America/Sao_Paulo")
    # Start boundary: 08:00:00 is OPEN
    dt_start = datetime(2026, 8, 26, 8, 0, tzinfo=tz)
    is_open_start, _, _ = is_window_open(sample_policy, current_dt=dt_start)
    assert is_open_start is True

    # End boundary: 20:00:00 is CLOSED (window is [start, end))
    dt_end = datetime(2026, 8, 26, 20, 0, tzinfo=tz)
    is_open_end, _, _ = is_window_open(sample_policy, current_dt=dt_end)
    assert is_open_end is False


def test_window_guard_disabled_in_policy(sample_policy):
    sample_policy["scheduler"]["enabled"] = False
    is_open, reason, _ = is_window_open(sample_policy)
    assert is_open is False
    assert reason == "scheduler_disabled"


def test_window_guard_manual_override(sample_policy):
    sample_policy["scheduler"]["enabled"] = False
    tz = ZoneInfo("America/Sao_Paulo")
    dt = datetime(2026, 8, 26, 3, 0, tzinfo=tz)
    is_open, reason, meta = is_window_open(sample_policy, current_dt=dt, is_manual_override=True)
    assert is_open is True
    assert reason == "manual_workflow_dispatch"
    assert meta.get("override") is True


def test_window_guard_overnight_window():
    overnight_policy = {
        "scheduler": {
            "enabled": True,
            "timezone": "America/Sao_Paulo",
            "start": "22:00",
            "end": "06:00"
        }
    }
    tz = ZoneInfo("America/Sao_Paulo")
    # 23:00 -> inside
    dt_night = datetime(2026, 8, 26, 23, 0, tzinfo=tz)
    assert is_window_open(overnight_policy, current_dt=dt_night)[0] is True

    # 02:00 -> inside
    dt_early = datetime(2026, 8, 26, 2, 0, tzinfo=tz)
    assert is_window_open(overnight_policy, current_dt=dt_early)[0] is True

    # 12:00 -> outside
    dt_day = datetime(2026, 8, 26, 12, 0, tzinfo=tz)
    assert is_window_open(overnight_policy, current_dt=dt_day)[0] is False


# ----------------------------------------------------------------------
# Pilar 3: State & Persistence Unit Tests
# ----------------------------------------------------------------------

def test_state_lifecycle(tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    import scheduler.state as state_mod
    monkeypatch.setattr(state_mod, "STATUS_FILE", status_file)

    # 1. Initial load
    init_status = state_mod.load_status()
    assert init_status["status"] == "IDLE"
    assert init_status["stats"]["total_runs"] == 0

    # 2. Start cycle
    started = state_mod.start_cycle("cycle_test_001")
    assert started["status"] == "PREFLIGHT"
    assert started["current_cycle_id"] == "cycle_test_001"
    assert started["stats"]["total_runs"] == 1

    # 3. Update phase
    phase_state = state_mod.update_phase("VALIDATING_PROPOSAL")
    assert phase_state["status"] == "VALIDATING_PROPOSAL"

    # 4. Record Success
    success_state = state_mod.record_success(
        cycle_id="cycle_test_001",
        proposal_id="prop_test_01",
        question_id="q_test_01",
        branch="agent/evolution-test",
        pr_url="https://github.com/test/pr/1"
    )
    assert success_state["status"] == "IDLE"
    assert success_state["last_proposal_id"] == "prop_test_01"
    assert "prop_test_01" in success_state["processed_proposals"]
    assert success_state["stats"]["successful_runs"] == 1
    assert success_state["consecutive_failures"] == 0

    # 5. Record Failure
    fail_state = state_mod.record_failure("Schema validation error", stop_reason="validation_error")
    assert fail_state["status"] == "FAILED"
    assert fail_state["last_error"] == "Schema validation error"
    assert fail_state["consecutive_failures"] == 1
    assert fail_state["stats"]["failed_runs"] == 1

    # 6. Record Skip
    skip_state = state_mod.record_skip("outside_window")
    assert skip_state["status"] == "SKIPPED"
    assert skip_state["stats"]["skipped_runs"] == 1


# ----------------------------------------------------------------------
# Pilar 6: Quality Gate Unit Tests
# ----------------------------------------------------------------------

def test_quality_gate_passes_on_clean_repository():
    all_passed, results = run_quality_gates(verbose=False)
    for r in results:
        assert r["passed"] is True, f"Gate {r['gate']} failed with: stderr={r.get('stderr')} stdout={r.get('stdout')}"
    assert all_passed is True
    assert len(results) == 7


# ----------------------------------------------------------------------
# Pilar 4, 8 & 10: Orchestrator Idempotency & Error Handling Tests
# ----------------------------------------------------------------------

def test_orchestrator_skips_when_window_closed(tmp_path):
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps({
        "scheduler": {
            "enabled": False,
            "timezone": "America/Sao_Paulo",
            "start": "08:00",
            "end": "20:00"
        }
    }))
    orch = EvolutionOrchestrator(policy_path=policy_file, skip_git=True, skip_preflight=True)
    res = orch.execute_cycle()
    assert res["status"] == "SKIPPED"
    assert "scheduler_disabled" in res["reason"]


def test_orchestrator_stops_when_max_rejections_reached(tmp_path, monkeypatch):
    import scheduler.state as state_mod
    state_mod.save_status({"status": "IDLE", "consecutive_failures": 2, "stats": {"total_runs": 2, "successful_runs": 0, "failed_runs": 2, "skipped_runs": 0}})

    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps({
        "scheduler": {"enabled": True, "timezone": "America/Sao_Paulo", "start": "00:00", "end": "23:59"},
        "limits": {"max_consecutive_rejections": 2}
    }))

    orch = EvolutionOrchestrator(policy_path=policy_file, skip_git=True, skip_preflight=True)
    res = orch.execute_cycle()
    assert res["status"] == "SKIPPED"
    assert res["reason"] == "consecutive_failures_limit_reached"


def test_orchestrator_rejects_low_confidence_proposal(tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    proposal_file = tmp_path / "proposal.json"
    proposal_file.write_text(json.dumps({
        "status": "PROPOSAL_READY",
        "proposal": {
            "proposal_id": "prop_low_conf",
            "confidence": 0.65  # Below 0.80 threshold
        }
    }))

    import scheduler.state as state_mod
    monkeypatch.setattr(state_mod, "STATUS_FILE", status_file)
    import scheduler.orchestrator as orch_mod
    monkeypatch.setattr(orch_mod, "PROPOSAL_OUTPUT_FILE", proposal_file)

    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps({
        "scheduler": {"enabled": True, "timezone": "America/Sao_Paulo", "start": "00:00", "end": "23:59"},
        "limits": {"max_consecutive_rejections": 5, "minimum_confidence_in_proposal": 0.8}
    }))

    def mock_runner(cmd):
        return 0, "OK", ""

    orch = EvolutionOrchestrator(
        policy_path=policy_file,
        skip_git=True,
        skip_preflight=True,
        force_window=True,
        runner_fn=mock_runner
    )
    res = orch.execute_cycle()
    assert res["status"] == "FAILED"
    assert res["reason"] == "confidence_below_threshold"
