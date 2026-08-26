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
