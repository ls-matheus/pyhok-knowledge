from __future__ import annotations

import json
import math
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.epistemic.judge import BlindEpistemicJudge, sanitize_proposal_for_judge
from evolution.epistemic.verifier import EvidenceVerifier, validate_provenance
from evolution.epistemic.critic import AdversarialCritic
from evolution.epistemic.red_team import AlternativeExplanationAgent
from evolution.epistemic.quarantine import record_quarantined_claim, check_prior_rejections
from evolution.epistemic.review_chamber import EpistemicReviewChamber


# ---------------------------------------------------------------------------
# 1. Generator Zero Authority & Sanitization Blindness
# ---------------------------------------------------------------------------

def test_constitution_generator_has_zero_authority():
    judge = BlindEpistemicJudge()
    hostile_proposal = {
        "confidence": 1.0,
        "novelty_score": 1.0,
        "coverage_gain": 1.0,
        "self_assessment": "DEFINITIVE_TRUTH",
        "question": {
            "id": "q_hostile",
            "epistemic_status": "EXTERNAL_FACT",
            "hypothesis": "Hostile self-certified claim.",
            "required_signals": ["sig_test_pointer_velocity"]
        }
    }
    critic_review = {
        "passes_adversarial_check": False,
        "severity_score": 0.85,
        "challenges": ["Unfounded causal leap."]
    }
    verifier_review = {
        "passes_verification": False,
        "derivation_depth": 0,
        "independent_evidence_count": 0,
        "errors": ["Missing roots"]
    }

    ruling = judge.judge(hostile_proposal, critic_review, verifier_review)
    assert ruling["decision"] == "REJECT"
    assert ruling["assigned_epistemic_status"] == "SPECULATION"


def test_constitution_judge_blind_to_generator_metrics():
    judge = BlindEpistemicJudge()
    base_prop = {
        "question": {
            "id": "q_blind_test",
            "hypothesis": "Focus stability decreases under fatigue, controlling for dpi scaling and sensor noise.",
            "required_signals": ["sig_test_pointer_velocity"]
        }
    }
    critic_rev = {"passes_adversarial_check": True, "severity_score": 0.0, "challenges": [], "contradictions": []}
    verifier_rev = {
        "passes_verification": True, "derivation_depth": 1, "independent_evidence_count": 1,
        "evidence_strength_score": 1.0, "independence_score": 1.0, "provenance_integrity_score": 1.0,
        "eligible_for_derived_status": False, "circularity_detected": False, "errors": []
    }
    red_rev = {"passes_red_team_check": True, "resistance_to_alternatives": 0.9, "parsimony_score": 1.0, "alternative_hypotheses": []}

    baseline_ruling = judge.judge(base_prop, critic_rev, verifier_rev, red_rev)

    hostile_variations = [
        {"confidence": 0.0, "novelty_score": 0.0},
        {"confidence": 1.0, "novelty_score": 1.0},
        {"confidence": -1e9, "novelty_score": float("inf")},
        {"CONFIDENCE": 1.0, "Novelty_Score": 0.99},
        {"nested": {"confidence": 1.0, "deep": {"generator_score": 0.99}}},
        {"predicted_metrics": {"novelty": 1.0, "confidence": 1.0}},
    ]

    for var in hostile_variations:
        mutated = dict(base_prop)
        mutated.update(var)
        ruling = judge.judge(mutated, critic_rev, verifier_rev, red_rev)
        assert ruling["decision"] == baseline_ruling["decision"]
        assert ruling["assigned_epistemic_status"] == baseline_ruling["assigned_epistemic_status"]
        assert ruling["epistemic_vector"] == baseline_ruling["epistemic_vector"]
        assert ruling["epistemic_score"] == baseline_ruling["epistemic_score"]


# ---------------------------------------------------------------------------
# 2. Reviewer Isolation & Concurrency
# ---------------------------------------------------------------------------

def test_constitution_reviewer_isolation_and_parallelism(tmp_path):
    rej_file = tmp_path / "rejected_claims.jsonl"
    chamber = EpistemicReviewChamber(quarantine_file=rej_file, parallel_workers=4)

    proposal = {
        "proposal_id": "prop_iso_01",
        "question": {
            "id": "q_iso_01",
            "hypothesis": "Visual fixation variance indicates mental workload, controlling for screen glare and ambient distraction.",
            "required_signals": ["sig_gaze_fixation_duration_v1"],
            "evaluation_trigger": {
                "rules": [{"signal_id": "sig_gaze_fixation_duration_v1", "operator": ">", "threshold": 250, "window_ms": 100}]
            },
            "provenance": {
                "derived_from": [],
                "evidence_roots": ["sig_gaze_fixation_duration_v1"]
            }
        }
    }

    res = chamber.review(proposal)
    assert res["decision"] in ("ACCEPT", "QUARANTINE", "REJECT")
    assert "critic_review" in res
    assert "verifier_review" in res
    assert "red_team_review" in res
    assert "memory_review" in res


# ---------------------------------------------------------------------------
# 3. Transitive DAG & Provenance Integrity
# ---------------------------------------------------------------------------

def test_constitution_provenance_must_be_acyclic():
    verifier = EvidenceVerifier()
    # Deep transitive cycle: A -> B -> C -> D -> A
    knowledge_state = {
        "questions": [
            {"id": "q_b", "provenance": {"derived_from": ["q_c"]}},
            {"id": "q_c", "provenance": {"derived_from": ["q_d"]}},
            {"id": "q_d", "provenance": {"derived_from": ["q_a"]}},
        ]
    }
    proposal = {
        "question": {
            "id": "q_a",
            "required_signals": ["sig_s1"],
            "provenance": {
                "derived_from": ["q_b"],
                "evidence_roots": ["sig_s1"]
            }
        }
    }
    res = verifier.verify_provenance(proposal, knowledge_state)
    assert res["circularity_detected"] is True
    assert res["passes_verification"] is False


def test_constitution_evidence_is_not_derivation():
    verifier = EvidenceVerifier()
    # Has depth > 0, but no empirical grounding / zero roots
    proposal = {
        "question": {
            "id": "q_unrooted",
            "required_signals": [],
            "provenance": {
                "derived_from": ["q_parent"],
                "evidence_roots": []
            }
        }
    }
    res = verifier.verify_provenance(proposal)
    assert res["eligible_for_derived_status"] is False


# ---------------------------------------------------------------------------
# 4. Active Negative Memory & Polarity Sensitivity
# ---------------------------------------------------------------------------

def test_constitution_rejected_claim_cannot_silently_reappear(tmp_path):
    rej_file = tmp_path / "rejected_claims.jsonl"
    prior_proposal = {
        "proposal_id": "prop_past_fail",
        "question": {"hypothesis": "Rapid saccade rate confirms catastrophic cognitive fatigue."}
    }
    record_quarantined_claim(
        prior_proposal,
        judge_ruling={"decision": "REJECT", "quarantine_reason": "DIAGNOSTIC_OVERREACH", "epistemic_score": 0.0},
        file_path=rej_file
    )

    repeat_proposal = {
        "proposal_id": "prop_repeat_attempt",
        "question": {"hypothesis": "Rapid saccade rate confirms catastrophic cognitive fatigue."}
    }
    res = check_prior_rejections(repeat_proposal, file_path=rej_file)
    assert res["has_prior_rejection"] is True
    assert res["match_type"] == "EXACT_MATCH"


def test_constitution_legitimate_novelty_not_blocked_by_negation(tmp_path):
    rej_file = tmp_path / "rejected_claims.jsonl"
    # Past claim affirmed correlation
    prior_proposal = {
        "proposal_id": "prop_affirmed_past",
        "question": {"hypothesis": "Increased pupil diameter indicates cognitive overload."}
    }
    record_quarantined_claim(
        prior_proposal,
        judge_ruling={"decision": "REJECT", "quarantine_reason": "UNRESOLVED_CONFOUNDERS", "epistemic_score": 0.3},
        file_path=rej_file
    )

    # New claim tests the negation / independence
    inverted_proposal = {
        "proposal_id": "prop_inverted_novel",
        "question": {"hypothesis": "Increased pupil diameter does not indicate cognitive overload."}
    }
    res = check_prior_rejections(inverted_proposal, file_path=rej_file)
    assert res["has_prior_rejection"] is False


# ---------------------------------------------------------------------------
# 5. Score Bounds, Invariants & Chaos Safety
# ---------------------------------------------------------------------------

def test_constitution_all_scores_strictly_bounded_0_to_1():
    judge = BlindEpistemicJudge()
    critic_rev = {"passes_adversarial_check": True, "severity_score": float("nan"), "logical_consistency_score": float("inf")}
    verifier_rev = {"passes_verification": True, "derivation_depth": 1, "independent_evidence_count": 1, "evidence_strength_score": -99.0}
    red_rev = {"passes_red_team_check": True, "resistance_to_alternatives": 999.0, "parsimony_score": float("-inf")}

    ruling = judge.judge({"question": {"id": "q_math"}}, critic_rev, verifier_rev, red_rev)
    for dim, score in ruling["epistemic_vector"].items():
        assert 0.0 <= score <= 1.0, f"Dimension {dim} out of bounds: {score}"
        assert math.isfinite(score)
    assert 0.0 <= ruling["epistemic_score"] <= 1.0
    assert math.isfinite(ruling["epistemic_score"])


def test_constitution_fail_closed_on_malformed_and_hostile_inputs():
    # Cyclical Python Object
    cyclic_obj: dict = {"question": {}}
    cyclic_obj["question"]["self_ref"] = cyclic_obj

    sanitized = sanitize_proposal_for_judge(cyclic_obj)
    assert sanitized is not None

    chamber = EpistemicReviewChamber()
    res = chamber.review(None)
    assert res["decision"] == "REJECT"


# ---------------------------------------------------------------------------
# 6. Deep Forensic Hardening Tests (Non-Mutation, Idempotence, Transitive 5-Node)
# ---------------------------------------------------------------------------

def test_constitution_sanitizer_does_not_mutate_original_object():
    original_proposal = {
        "confidence": 0.95,
        "question": {
            "id": "q_immutability",
            "hypothesis": "Hypothesis testing sanitizer immutability.",
            "nested_weights": {"internal_weights": 0.5, "valid_param": 10}
        }
    }
    serialized_before = json.dumps(original_proposal, sort_keys=True)
    sanitized = sanitize_proposal_for_judge(original_proposal)
    serialized_after = json.dumps(original_proposal, sort_keys=True)

    # Assert original proposal was not modified in-place
    assert serialized_before == serialized_after
    assert "confidence" not in sanitized
    assert "confidence" in original_proposal


def test_constitution_sanitizer_idempotence():
    proposal = {
        "confidence": 0.99,
        "question": {
            "id": "q_idempotent",
            "hypothesis": "Testing idempotence.",
            "internal_weights": [1, 2, 3]
        }
    }
    pass1 = sanitize_proposal_for_judge(proposal)
    pass2 = sanitize_proposal_for_judge(pass1)
    assert pass1 == pass2


def test_constitution_review_chamber_does_not_mutate_input_proposal(tmp_path):
    rej_file = tmp_path / "rej.jsonl"
    chamber = EpistemicReviewChamber(quarantine_file=rej_file)
    original_input = {
        "proposal_id": "prop_immutable_check",
        "question": {
            "id": "q_immutable_check",
            "hypothesis": "Hypothesis about pointer velocity, controlling for dpi scaling and sensor noise.",
            "required_signals": ["sig_test_pointer_velocity"],
            "evaluation_trigger": {
                "rules": [{"signal_id": "sig_test_pointer_velocity", "operator": ">", "threshold": 0.5, "window_ms": 100}]
            },
            "provenance": {
                "derived_from": [],
                "evidence_roots": ["sig_test_pointer_velocity"]
            }
        }
    }
    serialized_before = json.dumps(original_input, sort_keys=True)
    res = chamber.review(original_input)
    serialized_after = json.dumps(original_input, sort_keys=True)

    assert serialized_before == serialized_after
    assert res["decision"] == "ACCEPT"
    # Enriched proposal returned has epistemic_status attached
    assert "epistemic_status" in res["reviewed_proposal"]["question"]
    # But original caller dictionary remains untouched
    assert "epistemic_status" not in original_input["question"]


def test_constitution_concurrent_jsonl_append_safety(tmp_path):
    import concurrent.futures
    rej_file = tmp_path / "concurrent_rej.jsonl"

    def write_claim(idx: int):
        prop = {"proposal_id": f"prop_conc_{idx}", "question": {"hypothesis": f"Hypothesis {idx}"}}
        ruling = {"decision": "QUARANTINE", "quarantine_reason": f"REASON_{idx}", "epistemic_score": 0.5}
        record_quarantined_claim(prop, ruling, file_path=rej_file)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write_claim, range(24)))

    assert rej_file.exists()
    lines = [line.strip() for line in rej_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 24
    for l in lines:
        parsed = json.loads(l)
        assert "proposal_id" in parsed
        assert "decision" in parsed


def test_constitution_transitive_acyclic_five_node_cycle():
    verifier = EvidenceVerifier()
    # 5-node cycle: A -> B -> C -> D -> E -> A
    knowledge_state = {
        "questions": [
            {"id": "q_b", "provenance": {"derived_from": ["q_c"]}},
            {"id": "q_c", "provenance": {"derived_from": ["q_d"]}},
            {"id": "q_d", "provenance": {"derived_from": ["q_e"]}},
            {"id": "q_e", "provenance": {"derived_from": ["q_a"]}},
        ]
    }
    proposal = {
        "question": {
            "id": "q_a",
            "required_signals": ["sig_s1"],
            "provenance": {
                "derived_from": ["q_b"],
                "evidence_roots": ["sig_s1"]
            }
        }
    }
    res = verifier.verify_provenance(proposal, knowledge_state)
    assert res["circularity_detected"] is True
    assert res["passes_verification"] is False
