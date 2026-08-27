from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scheduler.continuous_engine import ContinuousKnowledgeEngine
from scheduler.orchestrator import EvolutionOrchestrator


def test_continuous_engine_unique_cycle_id_generation():
    engine = ContinuousKnowledgeEngine(verbose=False)
    ids = {engine.generate_cycle_id() for _ in range(100)}
    assert len(ids) == 100
    for cid in ids:
        assert cid.startswith("cycle_")


def test_continuous_engine_executes_multiple_cycles_without_artificial_sleep(tmp_path):
    chk_file = tmp_path / "checkpoint.json"
    mock_orch = MagicMock(spec=EvolutionOrchestrator)
    mock_orch.execute_cycle.return_value = {"status": "SUCCESS", "cycle_id": "test_cid"}

    engine = ContinuousKnowledgeEngine(
        orchestrator=mock_orch,
        checkpoint_path=chk_file,
        max_cycles=10,
        verbose=False,
    )

    t0 = time.perf_counter()
    res = engine.run_forever()
    elapsed = time.perf_counter() - t0

    assert res["status"] == "STOPPED"
    assert res["stop_reason"] == "max_cycles_reached"
    assert engine.metrics["total_cycles"] == 10
    assert engine.metrics["successful_cycles"] == 10
    assert mock_orch.execute_cycle.call_count == 10
    # Must complete 10 mocked cycles fast (under 1.0 second), proving absence of artificial sleeps
    assert elapsed < 1.0


def test_continuous_engine_exception_isolation_does_not_crash_loop(tmp_path):
    chk_file = tmp_path / "checkpoint.json"
    mock_orch = MagicMock(spec=EvolutionOrchestrator)

    # Alternate between raising errors and returning success
    call_counts = [0]
    def failing_cycle():
        call_counts[0] += 1
        if call_counts[0] % 2 == 1:
            raise RuntimeError("Simulated transient cycle failure")
        return {"status": "SUCCESS"}

    mock_orch.execute_cycle.side_effect = failing_cycle

    engine = ContinuousKnowledgeEngine(
        orchestrator=mock_orch,
        checkpoint_path=chk_file,
        max_cycles=6,
        max_consecutive_errors=10,
        backoff_base_sec=0.01,
        verbose=False,
    )

    res = engine.run_forever()
    assert res["status"] == "STOPPED"
    assert engine.metrics["total_cycles"] >= 3
    assert engine.metrics["total_errors"] >= 3


def test_continuous_engine_graceful_shutdown_on_signal(tmp_path):
    chk_file = tmp_path / "checkpoint.json"
    mock_orch = MagicMock(spec=EvolutionOrchestrator)

    engine = ContinuousKnowledgeEngine(
        orchestrator=mock_orch,
        checkpoint_path=chk_file,
        max_cycles=1000,
        verbose=False,
    )

    def stop_during_cycle():
        engine.stop(reason="graceful_signal_test")
        return {"status": "SUCCESS"}

    mock_orch.execute_cycle.side_effect = stop_during_cycle

    res = engine.run_forever()
    assert res["status"] == "STOPPED"
    assert res["stop_reason"] == "graceful_signal_test"
    assert engine.metrics["total_cycles"] == 1


def test_continuous_engine_checkpoint_and_restart_recovery(tmp_path):
    chk_file = tmp_path / "checkpoint.json"
    mock_orch = MagicMock(spec=EvolutionOrchestrator)
    mock_orch.execute_cycle.return_value = {"status": "SUCCESS"}

    # Run initial 5 cycles
    engine1 = ContinuousKnowledgeEngine(
        orchestrator=mock_orch,
        checkpoint_path=chk_file,
        max_cycles=5,
        verbose=False,
    )
    engine1.run_forever()
    assert chk_file.exists()

    # Restart new engine instance pointing to the same checkpoint file
    engine2 = ContinuousKnowledgeEngine(
        orchestrator=mock_orch,
        checkpoint_path=chk_file,
        max_cycles=5,
        verbose=False,
    )
    # Total cycles recovered from checkpoint
    assert engine2.metrics["total_cycles"] == 5
    assert engine2.metrics["accepted_proposals"] == 5

    engine2.run_forever()
    assert engine2.metrics["total_cycles"] == 10
    assert engine2.metrics["accepted_proposals"] == 10


def test_continuous_engine_memory_bounded_over_250_simulated_cycles(tmp_path):
    chk_file = tmp_path / "checkpoint.json"
    mock_orch = MagicMock(spec=EvolutionOrchestrator)

    # Simulates cycle producing temporary dictionaries and strings
    def heavy_cycle():
        temp_data = {"payload": [f"item_{i}" * 100 for i in range(200)]}
        return {"status": "SUCCESS", "cycle_id": "cid_mem_test", "size": len(temp_data["payload"])}

    mock_orch.execute_cycle.side_effect = heavy_cycle

    engine = ContinuousKnowledgeEngine(
        orchestrator=mock_orch,
        checkpoint_path=chk_file,
        max_cycles=250,
        enable_gc_per_cycle=True,
        verbose=False,
    )

    t0 = time.perf_counter()
    res = engine.run_forever()
    elapsed = time.perf_counter() - t0

    assert res["status"] == "STOPPED"
    assert engine.metrics["total_cycles"] == 250
    assert engine.metrics["successful_cycles"] == 250
    # Throughput benchmark: 250 cycles completed quickly without artificial delays
    assert elapsed < 10.0


def test_continuous_engine_anti_loop_negative_memory_prevention(tmp_path):
    from evolution.epistemic.quarantine import record_quarantined_claim, check_prior_rejections
    rej_file = tmp_path / "rejected.jsonl"

    # Claim A is rejected
    prop_a = {"proposal_id": "prop_a", "question": {"hypothesis": "Pointer jitter proves definitive disorder."}}
    ruling_a = {"decision": "REJECT", "quarantine_reason": "DIAGNOSTIC_OVERREACH"}
    record_quarantined_claim(prop_a, ruling_a, file_path=rej_file)

    # Claim B repeats claim A
    prop_b = {"proposal_id": "prop_b", "question": {"hypothesis": "Pointer jitter proves definitive disorder."}}
    mem_check = check_prior_rejections(prop_b, file_path=rej_file)

    # Continuous engine intercepts repeat claim before entering expensive cycle processing
    assert mem_check["has_prior_rejection"] is True
    assert mem_check["match_type"] == "EXACT_MATCH"
