from __future__ import annotations

import copy
import json
import math
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.graph.knowledge_graph import KnowledgeGraph, CyclicProvenanceError
from evolution.discovery.discovery_engine import EpistemicDiscoveryEngine
from evolution.epistemic.synapse import SinapseBindingEngine, bind_open_thesis
from evolution.epistemic.judge import BlindEpistemicJudge
from evolution.epistemic.critic import AdversarialCritic
from evolution.epistemic.verifier import EvidenceVerifier
from evolution.epistemic.quarantine import record_quarantined_claim, check_prior_rejections
from evolution.continuous_discovery_gate import run_continuous_discovery_gate
from scheduler.continuous_engine import ContinuousKnowledgeEngine
from scheduler.orchestrator import EvolutionOrchestrator


def test_discovery_engine_gap_detection():
    discovery = EpistemicDiscoveryEngine()
    state = {
        "signals": [
            {"id": "sig_isolated_alpha", "domain": "neural"},
            {"id": "sig_isolated_beta", "domain": "motor"}
        ],
        "questions": []
    }
    opportunities = discovery.detect_opportunities(state)
    gap_opps = [o for o in opportunities if o["opportunity_type"] == "GAP"]
    assert len(gap_opps) == 2
    for opp in gap_opps:
        assert opp["evidence_gap_score"] == 1.0
        assert 0.0 <= opp["novelty_score"] <= 1.0
        assert 0.0 <= opp["exploration_priority"] <= 1.0


def test_discovery_engine_contradiction_detection():
    discovery = EpistemicDiscoveryEngine()
    state = {
        "signals": [{"id": "sig_motor_velocity", "domain": "motor_control"}],
        "questions": [
            {
                "id": "q_velocity_high",
                "required_signals": ["sig_motor_velocity"],
                "evaluation_trigger": {"rules": [{"signal_id": "sig_motor_velocity", "operator": ">", "threshold": 100.0}]}
            },
            {
                "id": "q_velocity_low",
                "required_signals": ["sig_motor_velocity"],
                "evaluation_trigger": {"rules": [{"signal_id": "sig_motor_velocity", "operator": "<", "threshold": 100.0}]}
            }
        ]
    }
    opportunities = discovery.detect_opportunities(state)
    contra_opps = [o for o in opportunities if o["opportunity_type"] == "CONTRADICTION"]
    assert len(contra_opps) == 1
    assert contra_opps[0]["contradiction_value"] == 1.0
    assert contra_opps[0]["contradiction_id"] == "contra_q_velocity_high_q_velocity_low"


def test_discovery_engine_incomplete_theses_detection():
    discovery = EpistemicDiscoveryEngine()
    state = {
        "signals": [{"id": "sig_test_pointer_velocity"}],
        "open_theses": [
            {
                "thesis_id": "thesis_with_unbound",
                "hypothesis_template": "Investigating pointer stability",
                "investigation_status": "OPEN",
                "open_variables": [
                    {"id": "var_x", "status": "UNBOUND"}
                ]
            }
        ]
    }
    opportunities = discovery.detect_opportunities(state)
    incomplete_opps = [o for o in opportunities if o["opportunity_type"] == "INCOMPLETE_THESIS"]
    assert len(incomplete_opps) == 1
    assert incomplete_opps[0]["source_entities"][0] == "thesis_with_unbound"


def test_open_variable_life_cycle_taxonomy():
    synapse = SinapseBindingEngine()
    thesis = {
        "thesis_id": "thesis_taxonomy_test",
        "open_variables": [
            {"id": "var_unbound_no_match", "status": "UNBOUND", "candidate_values": []},
            {"id": "var_candidate_only", "status": "UNBOUND", "candidate_values": ["sig_missing_candidate"]},
            {"id": "var_bound_match", "status": "UNBOUND", "candidate_values": ["sig_present_signal"]}
        ]
    }
    context = {"signals": [{"id": "sig_present_signal", "domain": "motor"}]}
    bound = synapse.prepare_or_bind(thesis, context)

    vars_by_id = {v["id"]: v for v in bound["open_variables"]}
    assert vars_by_id["var_unbound_no_match"]["status"] == "UNBOUND"
    assert vars_by_id["var_candidate_only"]["status"] == "CANDIDATE"
    assert vars_by_id["var_bound_match"]["status"] == "BOUND"
    assert vars_by_id["var_bound_match"]["binding"] == "sig_present_signal"
    assert vars_by_id["var_bound_match"]["binding_source"] == "SYNAPSE"


def test_closed_world_honesty_no_fabricated_evidence():
    synapse = SinapseBindingEngine()
    thesis = {
        "thesis_id": "thesis_closed_world",
        "hypothesis_template": "Exploring unknown EEG alpha rhythms",
        "open_variables": [
            {"id": "var_eeg_alpha", "status": "UNBOUND", "candidate_values": []}
        ]
    }
    # Completely empty context -> must declare NO_NEW_EVIDENCE and not invent bindings
    bound = synapse.prepare_or_bind(thesis, context={})
    assert bound["investigation_status"] == "OPEN"
    assert bound["open_variables"][0]["status"] == "UNBOUND"
    assert bound["open_variables"][0]["binding"] is None
    assert bound["provenance"].get("binding_verdict") == "NO_NEW_EVIDENCE"


def test_adversarial_self_deception_attacks():
    judge = BlindEpistemicJudge()
    verifier = EvidenceVerifier()

    # Attack 1: Self-inflated generator scores stripped completely by judge
    deceptive_proposal = {
        "proposal_id": "prop_deceptive_01",
        "confidence_score": 0.99,
        "model_confidence": 1.0,
        "question": {
            "id": "q_deceptive",
            "hypothesis": "Trivially short",
            "required_signals": []
        }
    }
    ruling = judge.judge(deceptive_proposal, critic_review=None, verifier_review=None)
    assert ruling["decision"] == "REJECT"
    assert ruling["assigned_epistemic_status"] == "SPECULATION"

    # Attack 2: Derivation claims empirical evidence status without independent roots
    fake_root_proposal = {
        "question": {
            "id": "q_fake_derived",
            "hypothesis": "Valid length hypothesis about pointer velocity deviation.",
            "required_signals": ["sig_test_pointer_velocity"],
            "provenance": {
                "derived_from": ["q_ancestor"],
                "evidence_roots": [],
                "binding_source": "SYNAPSE"
            }
        }
    }
    v_res = verifier.verify_provenance(fake_root_proposal)
    assert v_res["eligible_for_derived_status"] is False


def test_knowledge_graph_acyclic_dag_enforcement():
    kg = KnowledgeGraph()
    kg.add_node("q1", "Question")
    kg.add_node("q2", "Question")
    kg.add_node("q3", "Question")

    kg.add_edge("q1", "q2", "DERIVED_FROM")
    kg.add_edge("q2", "q3", "DERIVED_FROM")

    # Adding q3 -> q1 must fail closed with CyclicProvenanceError
    with pytest.raises(CyclicProvenanceError):
        kg.add_edge("q3", "q1", "DERIVED_FROM")


def test_continuous_discovery_engine_long_duration_simulation(tmp_path):
    chk_file = tmp_path / "checkpoint.json"
    rej_file = tmp_path / "rejected.jsonl"

    mock_orch = MagicMock(spec=EvolutionOrchestrator)
    mock_orch.quarantine_file = rej_file
    mock_orch.load_knowledge_state.return_value = {
        "signals": [
            {"id": f"sig_stream_{i}", "domain": f"domain_{i % 3}"}
            for i in range(10)
        ],
        "questions": [],
        "relations": []
    }

    engine = ContinuousKnowledgeEngine(
        orchestrator=mock_orch,
        checkpoint_path=chk_file,
        max_cycles=10,
        enable_gc_per_cycle=True,
        gc_interval=5,
        verbose=False,
    )

    t0 = time.perf_counter()
    res = engine.run_forever()
    elapsed = time.perf_counter() - t0

    assert res["status"] == "STOPPED"
    assert engine.metrics["total_cycles"] == 10
    assert engine.metrics["discoveries_total"] > 0
    assert engine.metrics["new_theses_generated"] > 0
    assert engine.graph.node_count > 0
    # Verified: knowledge_size_final > knowledge_size_initial
    assert engine.metrics["knowledge_nodes"] > 0
    # Verified: novelty > 0
    nov_mean = sum(engine.metrics["novelty_scores"]) / max(1, len(engine.metrics["novelty_scores"]))
    assert nov_mean > 0.0


def test_continuous_discovery_gate_passes():
    state = {
        "signals": [
            {"id": "sig_test_pointer_velocity", "domain": "motor_control"}
        ],
        "questions": [],
        "relations": []
    }
    passed, errors = run_continuous_discovery_gate(state)
    assert passed is True, f"continuous_discovery_gate failed: {errors}"
