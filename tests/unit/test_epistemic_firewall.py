from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.epistemic.critic import AdversarialCritic
from evolution.epistemic.verifier import EvidenceVerifier
from evolution.epistemic.judge import BlindEpistemicJudge
from evolution.epistemic.quarantine import record_quarantined_claim, read_rejected_claims
from evolution.epistemic.review_chamber import EpistemicReviewChamber
from evolution.epistemic_gate import check_epistemic_firewall


# ----------------------------------------------------------------------
# 1. Adversarial Critic Tests
# ----------------------------------------------------------------------

def test_adversarial_critic_rejects_diagnostic_language():
    critic = AdversarialCritic()
    proposal = {
        "question": {
            "id": "q_autism_test",
            "hypothesis": "The participant clearly has autism and requires clinical diagnosis.",
            "required_signals": ["sig_test_01"],
            "evaluation_trigger": {
                "rules": [{"signal_id": "sig_test_01", "operator": ">", "threshold": 0.5}]
            }
        }
    }
    review = critic.review_proposal(proposal)
    assert review["verdict"] == "FAIL"
    assert review["passes_adversarial_check"] is False
    assert any("forbidden term 'diagnosis'" in c for c in review["challenges"])


def test_adversarial_critic_detects_contradictions():
    critic = AdversarialCritic()
    knowledge_state = {
        "questions": [{
            "id": "q_existing_01",
            "required_signals": ["sig_motor_alpha"],
            "evaluation_trigger": {
                "rules": [{"signal_id": "sig_motor_alpha", "operator": "<", "threshold": 0.3}]
            }
        }]
    }
    proposal = {
        "question": {
            "id": "q_contradicting_02",
            "hypothesis": "Motor alpha activation indicates motor readiness.",
            "required_signals": ["sig_motor_alpha"],
            "evaluation_trigger": {
                "rules": [{"signal_id": "sig_motor_alpha", "operator": ">", "threshold": 0.3}]
            }
        }
    }
    review = critic.review_proposal(proposal, knowledge_state)
    assert len(review["contradictions"]) > 0
    assert review["passes_adversarial_check"] is False


# ----------------------------------------------------------------------
# 2. Evidence & Provenance Verifier Tests
# ----------------------------------------------------------------------

def test_evidence_verifier_derivation_depth():
    verifier = EvidenceVerifier(max_depth=3)
    knowledge_state = {
        "signals": [{"id": "sig_s1"}, {"id": "sig_s2"}],
        "questions": [
            {
                "id": "q_ancestor_1",
                "provenance": {"derivation_depth": 1, "derived_from": []}
            },
            {
                "id": "q_ancestor_2",
                "provenance": {"derivation_depth": 2, "derived_from": ["q_ancestor_1"]}
            }
        ]
    }
    proposal = {
        "question": {
            "id": "q_child_3",
            "required_signals": ["sig_s1"],
            "provenance": {
                "derived_from": ["q_ancestor_2"],
                "evidence_roots": ["sig_s1"]
            }
        }
    }
    res = verifier.verify_provenance(proposal, knowledge_state)
    assert res["derivation_depth"] == 3
    assert res["passes_verification"] is True


def test_evidence_verifier_detects_self_referential_circularity():
    verifier = EvidenceVerifier()
    proposal = {
        "question": {
            "id": "q_circular_node",
            "required_signals": ["sig_s1"],
            "provenance": {
                "derived_from": ["q_circular_node"],
                "evidence_roots": ["sig_s1"]
            }
        }
    }
    res = verifier.verify_provenance(proposal)
    assert res["circularity_detected"] is True
    assert res["passes_verification"] is False


# ----------------------------------------------------------------------
# 3. Blind Epistemic Judge Tests
# ----------------------------------------------------------------------

def test_blind_judge_blindness_to_generator_confidence():
    judge = BlindEpistemicJudge()
    proposal = {
        "confidence": 0.99,  # High confidence
        "novelty_score": 0.95,
        "question": {
            "id": "q_valid",
            "hypothesis": "Valid scientific hypothesis on motor tremor."
        }
    }
    # But critic raised fatal challenge
    critic_review = {
        "passes_adversarial_check": False,
        "severity_score": 0.80,
        "contradictions": [],
        "challenges": ["Severe logical jump in hypothesis."]
    }
    verifier_review = {
        "passes_verification": True,
        "derivation_depth": 1,
        "independent_evidence_count": 1,
        "circularity_detected": False,
        "errors": []
    }

    # Judge must REJECT despite 0.99 generator confidence
    ruling = judge.judge(proposal, critic_review, verifier_review)
    assert ruling["decision"] == "REJECT"
    assert "CRITIC_SEVERITY_TOO_HIGH" in ruling["quarantine_reason"]


def test_blind_judge_quarantines_deep_unanchored_derivation():
    judge = BlindEpistemicJudge()
    proposal = {"question": {"id": "q_deep", "hypothesis": "Hypothesis deep."}}
    critic_review = {
        "passes_adversarial_check": True,
        "severity_score": 0.0,
        "contradictions": [],
        "challenges": []
    }
    verifier_review = {
        "passes_verification": False,
        "derivation_depth": 4,  # Exceeds max depth 3
        "independent_evidence_count": 0,
        "circularity_detected": False,
        "errors": ["Derivation depth 4 exceeds limit with 0 roots"]
    }
    ruling = judge.judge(proposal, critic_review, verifier_review)
    assert ruling["decision"] == "QUARANTINE"
    assert ruling["assigned_epistemic_status"] == "HYPOTHESIS"
    assert "EXCEEDS_DERIVATION_DEPTH_LIMIT" in ruling["quarantine_reason"]


# ----------------------------------------------------------------------
# 4. Quarantine Registry Tests
# ----------------------------------------------------------------------

def test_quarantine_registry_records_rejected_claims(tmp_path):
    rej_file = tmp_path / "rejected_claims.jsonl"
    proposal = {
        "proposal_id": "prop_failed_01",
        "question": {"hypothesis": "Flawed hypothesis about gaze."}
    }
    ruling = {
        "decision": "QUARANTINE",
        "quarantine_reason": "UNRESOLVED_CHALLENGES",
        "assigned_epistemic_status": "HYPOTHESIS",
        "epistemic_score": 0.5
    }
    record_quarantined_claim(proposal, ruling, file_path=rej_file)

    stored = read_rejected_claims(file_path=rej_file)
    assert len(stored) == 1
    assert stored[0]["proposal_id"] == "prop_failed_01"
    assert stored[0]["decision"] == "QUARANTINE"


# ----------------------------------------------------------------------
# 5. Epistemic Firewall Quality Gate Tests
# ----------------------------------------------------------------------

def test_epistemic_firewall_gate_passes_on_valid_dataset():
    passed, errors = check_epistemic_firewall()
    assert passed is True, f"Epistemic gate failed with errors: {errors}"
    assert errors == []


def test_epistemic_firewall_gate_detects_circular_reinforcement(tmp_path):
    q_dir = tmp_path / "questions"
    r_dir = tmp_path / "relations"
    q_dir.mkdir()
    r_dir.mkdir()

    # Create mutual circular reinforcement A -> B and B -> A
    (r_dir / "rel_1.json").write_text(json.dumps({
        "source_question_id": "q_alpha",
        "target_question_id": "q_beta",
        "relation_type": "REINFORCES"
    }))
    (r_dir / "rel_2.json").write_text(json.dumps({
        "source_question_id": "q_beta",
        "target_question_id": "q_alpha",
        "relation_type": "REINFORCES"
    }))

    passed, errors = check_epistemic_firewall(questions_dir=q_dir, relations_dir=r_dir)
    assert passed is False
    assert any("CIRCULAR_REINFORCEMENT_DETECTED" in e for e in errors)


# ----------------------------------------------------------------------
# 6. Red-Team / Alternative Explanation Tests
# ----------------------------------------------------------------------

from evolution.epistemic.red_team import AlternativeExplanationAgent
from evolution.epistemic.quarantine import check_prior_rejections


def test_red_team_identifies_confounders_and_alternative_hypotheses():
    red_team = AlternativeExplanationAgent()
    proposal = {
        "question": {
            "id": "q_gaze_decay",
            "hypothesis": "Hypothesis proposing cognitive decay from raw gaze fixation without modeling screen glare.",
            "required_signals": ["sig_gaze_fixation_duration_v1"],
            "evaluation_trigger": {
                "rules": [{"signal_id": "sig_gaze_fixation_duration_v1", "operator": "<", "threshold": 200, "window_ms": 100}]
            }
        }
    }
    review = red_team.evaluate_alternatives(proposal)
    assert len(review["confounders_identified"]) > 0
    assert any("glare" in h or "distraction" in h or "fatigue" in h for h in review["alternative_hypotheses"])


def test_red_team_penalizes_overcomplicated_rules_occam_razor():
    red_team = AlternativeExplanationAgent()
    proposal = {
        "question": {
            "id": "q_complex",
            "hypothesis": "Complex hypothesis with 5 arbitrary rules.",
            "required_signals": ["sig_test_pointer_velocity"],
            "evaluation_trigger": {
                "rules": [
                    {"signal_id": "sig_test_pointer_velocity", "operator": ">", "threshold": 1.0, "window_ms": 10},
                    {"signal_id": "sig_test_pointer_velocity", "operator": "<", "threshold": 5.0, "window_ms": 20},
                    {"signal_id": "sig_test_pointer_velocity", "operator": ">", "threshold": 2.0, "window_ms": 30},
                    {"signal_id": "sig_test_pointer_velocity", "operator": "<", "threshold": 4.0, "window_ms": 40},
                    {"signal_id": "sig_test_pointer_velocity", "operator": ">", "threshold": 3.0, "window_ms": 50},
                ]
            }
        }
    }
    review = red_team.evaluate_alternatives(proposal)
    assert review["parsimony_score"] < 1.0
    assert any("Occam" in h or "complexity" in h or "simpler" in h for h in review["alternative_hypotheses"])


# ----------------------------------------------------------------------
# 7. Active Negative Memory & Multidimensional Vector Tests
# ----------------------------------------------------------------------

def test_active_negative_memory_detects_disguised_repetition(tmp_path):
    rej_file = tmp_path / "rejected_claims.jsonl"
    prior_proposal = {
        "proposal_id": "prop_old_fail_42",
        "question": {"hypothesis": "Persistent distal tremor indicates cognitive breakdown and attentional collapse."}
    }
    record_quarantined_claim(
        proposal=prior_proposal,
        judge_ruling={"decision": "REJECT", "quarantine_reason": "FATAL_CIRCULARITY_DETECTED", "epistemic_score": 0.0},
        file_path=rej_file
    )

    # New disguised proposal with high word overlap
    new_proposal = {
        "proposal_id": "prop_new_attempt",
        "question": {"hypothesis": "Persistent distal tremor indicates attentional breakdown and cognitive collapse."}
    }
    res = check_prior_rejections(new_proposal, file_path=rej_file)
    assert res["has_prior_rejection"] is True
    assert res["highest_similarity"] >= 0.70
    assert "prop_old_fail_42" in res["repetition_warning"]


def test_blind_judge_calculates_multidimensional_epistemic_vector():
    judge = BlindEpistemicJudge()
    proposal = {
        "question": {"id": "q_multidim", "hypothesis": "Valid empirical hypothesis."}
    }
    critic_review = {
        "passes_adversarial_check": True,
        "severity_score": 0.10,
        "contradictions": [],
        "challenges": []
    }
    verifier_review = {
        "passes_verification": True,
        "derivation_depth": 1,
        "independent_evidence_count": 2,
        "circularity_detected": False,
        "errors": []
    }
    red_team_review = {
        "passes_red_team_check": True,
        "resistance_to_alternatives": 0.85,
        "parsimony_score": 0.90,
        "alternative_hypotheses": []
    }

    ruling = judge.judge(
        proposal=proposal,
        critic_review=critic_review,
        verifier_review=verifier_review,
        red_team_review=red_team_review
    )
    assert ruling["decision"] == "ACCEPT"
    vec = ruling["epistemic_vector"]
    assert "evidence_strength" in vec
    assert "logical_consistency" in vec
    assert "independence" in vec
    assert "alternative_explanation_resistance" in vec
    assert "provenance_integrity" in vec
    assert vec["logical_consistency"] == 0.90
    assert vec["provenance_integrity"] == 1.0
    assert ruling["epistemic_score"] >= 0.80


# ----------------------------------------------------------------------
# 8. Judge Blindness Invariance Property Tests
# ----------------------------------------------------------------------

def test_judge_blindness_invariance_property():
    judge = BlindEpistemicJudge()
    critic_review = {
        "passes_adversarial_check": True,
        "severity_score": 0.0,
        "logical_consistency_score": 1.0,
        "contradiction_status_score": 1.0,
        "adversarial_robustness_score": 1.0,
        "contradictions": [],
        "challenges": []
    }
    verifier_review = {
        "passes_verification": True,
        "derivation_depth": 1,
        "independent_evidence_count": 2,
        "evidence_strength_score": 1.0,
        "independence_score": 1.0,
        "provenance_integrity_score": 1.0,
        "eligible_for_derived_status": True,
        "circularity_detected": False,
        "errors": []
    }
    red_team_review = {
        "passes_red_team_check": True,
        "resistance_to_alternatives": 0.90,
        "parsimony_score": 1.0,
        "alternative_hypotheses": []
    }

    baseline_proposal = {
        "question": {"id": "q_inv_01", "hypothesis": "Attentive response latency decreases with focus."}
    }
    baseline_ruling = judge.judge(baseline_proposal, critic_review, verifier_review, red_team_review)

    test_variations = [
        {"confidence": 0.0, "novelty_score": 0.0, "coverage_gain": 0.0},
        {"confidence": 1.0, "novelty_score": 1.0, "coverage_gain": 1.0},
        {"confidence": 0.9999, "novelty_score": 0.0001, "coverage_gain": 999999.0},
        {"generator_score": 0.5, "generator_verdict": "ALWAYS_ACCEPT", "self_assessment": "FLAWLESS"},
        {"predicted_metrics": {"novelty": 1.0, "confidence": 1.0}, "internal_weights": {"focus": 1.0}},
    ]

    for var in test_variations:
        mutated_prop = dict(baseline_proposal)
        mutated_prop.update(var)
        mutated_ruling = judge.judge(mutated_prop, critic_review, verifier_review, red_team_review)

        assert mutated_ruling["decision"] == baseline_ruling["decision"], f"Decision mutated for variation {var}"
        assert mutated_ruling["assigned_epistemic_status"] == baseline_ruling["assigned_epistemic_status"]
        assert mutated_ruling["epistemic_vector"] == baseline_ruling["epistemic_vector"]
        assert mutated_ruling["epistemic_score"] == baseline_ruling["epistemic_score"]


# ----------------------------------------------------------------------
# 9. Chamber Determinism (100 Runs Invariant)
# ----------------------------------------------------------------------

def test_review_chamber_100_runs_determinism(tmp_path):
    proposal = {
        "proposal_id": "prop_det_01",
        "question": {
            "id": "q_det_01",
            "hypothesis": "Pointer velocity variance reflects neuromuscular fatigue, controlling for dpi scaling and sensor noise.",
            "required_signals": ["sig_test_pointer_velocity"],
            "evaluation_trigger": {
                "rules": [{"signal_id": "sig_test_pointer_velocity", "operator": ">", "threshold": 0.8, "window_ms": 100}]
            },
            "provenance": {
                "derived_from": [],
                "evidence_roots": ["sig_test_pointer_velocity"]
            }
        }
    }

    first_rej = tmp_path / "first_rej.jsonl"
    first_chamber = EpistemicReviewChamber(quarantine_file=first_rej)
    first_result = first_chamber.review(proposal)
    first_dec = first_result["decision"]
    first_vec = first_result["judge_ruling"]["epistemic_vector"]
    first_score = first_result["judge_ruling"]["epistemic_score"]

    for i in range(100):
        iter_rej = tmp_path / f"iter_rej_{i}.jsonl"
        iter_chamber = EpistemicReviewChamber(quarantine_file=iter_rej)
        res = iter_chamber.review(proposal)
        assert res["decision"] == first_dec
        assert res["judge_ruling"]["epistemic_vector"] == first_vec
        assert res["judge_ruling"]["epistemic_score"] == first_score


# ----------------------------------------------------------------------
# 10. Concurrency & Thread-Safety Tests
# ----------------------------------------------------------------------

def test_review_chamber_parallel_concurrency_and_thread_safety(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    rej_file = tmp_path / "rejected_claims.jsonl"
    chamber = EpistemicReviewChamber(quarantine_file=rej_file, parallel_workers=4)

    proposals = [
        {
            "proposal_id": f"prop_conc_{i}",
            "question": {
                "id": f"q_conc_{i}",
                "hypothesis": f"Hypothesis variation {i} on gaze fixation.",
                "required_signals": ["sig_gaze_fixation_duration_v1"],
                "evaluation_trigger": {
                    "rules": [{"signal_id": "sig_gaze_fixation_duration_v1", "operator": ">", "threshold": 0.5, "window_ms": 100}]
                }
            }
        }
        for i in range(12)
    ]

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(chamber.review, proposals))

    assert len(results) == 12
    for r in results:
        assert r["decision"] in ("ACCEPT", "QUARANTINE", "REJECT")
        assert 0.0 <= r["judge_ruling"]["epistemic_score"] <= 1.0


# ----------------------------------------------------------------------
# 11. Strict Epistemic Status & Provenance Tests
# ----------------------------------------------------------------------

def test_derived_status_requires_strict_provenance_and_roots():
    verifier = EvidenceVerifier()
    # Case A: Has derivation depth > 0, but ZERO evidence roots
    proposal_no_roots = {
        "question": {
            "id": "q_no_roots",
            "required_signals": [],
            "provenance": {
                "derived_from": ["q_ancestor_1"],
                "evidence_roots": []
            }
        }
    }
    res_a = verifier.verify_provenance(proposal_no_roots)
    assert res_a["eligible_for_derived_status"] is False

    # Case B: Fully grounded with ancestor and evidence roots
    knowledge_state = {
        "signals": [{"id": "sig_grounded_01"}],
        "questions": [{"id": "q_ancestor_1", "provenance": {"derivation_depth": 1}}]
    }
    proposal_grounded = {
        "question": {
            "id": "q_grounded",
            "required_signals": ["sig_grounded_01"],
            "provenance": {
                "derived_from": ["q_ancestor_1"],
                "evidence_roots": ["sig_grounded_01"]
            }
        }
    }
    res_b = verifier.verify_provenance(proposal_grounded, knowledge_state)
    assert res_b["eligible_for_derived_status"] is True


def test_provenance_validation_detects_indirect_loops_and_broken_refs():
    verifier = EvidenceVerifier()
    knowledge_state = {
        "questions": [
            {"id": "q_node_b", "provenance": {"derived_from": ["q_node_c"]}},
            {"id": "q_node_c", "provenance": {"derived_from": ["q_node_a"]}},
        ]
    }
    # Proposal q_node_a derives from q_node_b -> indirect cycle A -> B -> C -> A
    proposal = {
        "question": {
            "id": "q_node_a",
            "required_signals": ["sig_s1"],
            "provenance": {
                "derived_from": ["q_node_b"],
                "evidence_roots": ["sig_s1"]
            }
        }
    }
    res = verifier.verify_provenance(proposal, knowledge_state)
    assert res["circularity_detected"] is True
    assert res["passes_verification"] is False


# ----------------------------------------------------------------------
# 12. Score Invariants & Chaos Hostile Inputs
# ----------------------------------------------------------------------

def test_mathematical_score_invariants_bounded_0_to_1():
    judge = BlindEpistemicJudge()
    critic = AdversarialCritic()
    verifier = EvidenceVerifier()
    red_team = AlternativeExplanationAgent()

    # Extreme input
    proposal = {
        "confidence": float("inf"),
        "novelty_score": float("-inf"),
        "question": {
            "id": "q_extreme",
            "hypothesis": "Extreme score hypothesis with unusual syntax.",
            "required_signals": ["sig_test_pointer_velocity"],
            "evaluation_trigger": {
                "rules": [{"signal_id": "sig_test_pointer_velocity", "operator": ">", "threshold": 1e9, "window_ms": 10}]
            }
        }
    }
    c_res = critic.review_proposal(proposal)
    v_res = verifier.verify_provenance(proposal)
    r_res = red_team.evaluate_alternatives(proposal)
    j_res = judge.judge(proposal, c_res, v_res, r_res)

    for k, v in j_res["epistemic_vector"].items():
        assert 0.0 <= v <= 1.0, f"Vector dimension {k} out of bounds: {v}"
    assert 0.0 <= j_res["epistemic_score"] <= 1.0


def test_chaos_malformed_and_hostile_proposals():
    chamber = EpistemicReviewChamber()

    hostile_cases = [
        None,
        {},
        {"question": None},
        {"question": "not a dictionary"},
        {"question": {"hypothesis": ""}},
        {"question": {"hypothesis": "A" * 50000, "required_signals": ["sig_unknown"]}},
        {"question": {"hypothesis": "Unicode: 🤖 🧠 💥 🚀 \u0000\uffff", "required_signals": None}},
        {"question": {"hypothesis": "Valid text", "evaluation_trigger": {"rules": "invalid"}}},
        {"question": {"hypothesis": "Valid text", "evaluation_trigger": {"rules": [{"threshold": None}]}}},
    ]

    for case in hostile_cases:
        res = chamber.review(case)
        assert res["decision"] in ("REJECT", "QUARANTINE")
        assert 0.0 <= res["judge_ruling"]["epistemic_score"] <= 1.0
