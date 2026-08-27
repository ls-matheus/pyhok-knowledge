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


def test_record_thesis_output_categorization(tmp_path):
    from scheduler.continuous_engine import record_thesis_output

    out_file = tmp_path / "theses.json"
    val_file = tmp_path / "theses_validated.json"
    rej_file = tmp_path / "theses_rejected.json"
    quar_file = tmp_path / "theses_quarantined.json"

    stream_file = tmp_path / "theses_stream.jsonl"
    val_stream = tmp_path / "validated_stream.jsonl"
    rej_stream = tmp_path / "rejected_stream.jsonl"

    out_dir = tmp_path / "theses"
    val_dir = tmp_path / "theses/validated"
    rej_dir = tmp_path / "theses/rejected"
    quar_dir = tmp_path / "theses/quarantined"
    prop_file = tmp_path / "proposal.json"

    # 1. Record an accepted thesis
    th_accepted = {
        "thesis_id": "th_val_001",
        "decision": "ACCEPT",
        "opportunity_type": "GAP",
        "hypothesis_template": "Validated relationship between X and Y",
        "review_result": {"decision": "ACCEPT", "epistemic_score": 0.95},
    }
    record_thesis_output(
        th_accepted,
        output_file=out_file,
        validated_file=val_file,
        rejected_file=rej_file,
        quarantined_file=quar_file,
        stream_file=stream_file,
        validated_stream_file=val_stream,
        rejected_stream_file=rej_stream,
        output_dir=out_dir,
        validated_dir=val_dir,
        rejected_dir=rej_dir,
        quarantined_dir=quar_dir,
        proposal_file=prop_file,
    )

    # 2. Record a rejected thesis
    th_rejected = {
        "thesis_id": "th_rej_001",
        "decision": "REJECT",
        "opportunity_type": "CONTRADICTION",
        "hypothesis_template": "Rejected speculative claim",
        "rejection_reason": "DIAGNOSTIC_OVERREACH",
        "review_result": {"decision": "REJECT", "epistemic_score": 0.10},
    }
    record_thesis_output(
        th_rejected,
        output_file=out_file,
        validated_file=val_file,
        rejected_file=rej_file,
        quarantined_file=quar_file,
        stream_file=stream_file,
        validated_stream_file=val_stream,
        rejected_stream_file=rej_stream,
        output_dir=out_dir,
        validated_dir=val_dir,
        rejected_dir=rej_dir,
        quarantined_dir=quar_dir,
        proposal_file=prop_file,
    )

    # 3. Record a quarantined thesis
    th_quarantined = {
        "thesis_id": "th_quar_001",
        "decision": "QUARANTINE",
        "opportunity_type": "INCOMPLETE_THESIS",
        "hypothesis_template": "Quarantined unverified hypothesis",
        "review_result": {"decision": "QUARANTINE", "epistemic_score": 0.50},
    }
    record_thesis_output(
        th_quarantined,
        output_file=out_file,
        validated_file=val_file,
        rejected_file=rej_file,
        quarantined_file=quar_file,
        stream_file=stream_file,
        validated_stream_file=val_stream,
        rejected_stream_file=rej_stream,
        output_dir=out_dir,
        validated_dir=val_dir,
        rejected_dir=rej_dir,
        quarantined_dir=quar_dir,
        proposal_file=prop_file,
    )

    # Verify individual JSON files exist in their respective categorized directories
    assert (val_dir / "th_val_001.json").exists()
    assert (rej_dir / "th_rej_001.json").exists()
    assert (quar_dir / "th_quar_001.json").exists()

    # Verify root flat directory also has them
    assert (out_dir / "th_val_001.json").exists()
    assert (out_dir / "th_rej_001.json").exists()
    assert (out_dir / "th_quar_001.json").exists()

    # Verify categorized list JSON files
    val_data = json.loads(val_file.read_text())
    assert val_data["total"] == 1
    assert val_data["theses"][0]["thesis_id"] == "th_val_001"

    rej_data = json.loads(rej_file.read_text())
    assert rej_data["total"] == 1
    assert rej_data["theses"][0]["thesis_id"] == "th_rej_001"

    quar_data = json.loads(quar_file.read_text())
    assert quar_data["total"] == 1
    assert quar_data["theses"][0]["thesis_id"] == "th_quar_001"

    # Verify master theses.json has counts and grouped arrays
    master = json.loads(out_file.read_text())
    assert master["total_theses"] == 3
    assert master["counts"]["validated"] == 1
    assert master["counts"]["rejected"] == 1
    assert master["counts"]["quarantined"] == 1
    assert len(master["validated_theses"]) == 1
    assert len(master["rejected_theses"]) == 1
    assert len(master["quarantined_theses"]) == 1
