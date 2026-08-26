"""
PyHok Epistemic Multi-Agent Architecture
Separation of duties: Generator -> Adversarial Critic + Evidence Verifier -> Blind Judge.
"""
from evolution.epistemic.critic import AdversarialCritic, run_adversarial_critic
from evolution.epistemic.verifier import EvidenceVerifier, verify_epistemic_provenance, validate_provenance
from evolution.epistemic.red_team import AlternativeExplanationAgent, run_alternative_explanation_agent
from evolution.epistemic.judge import BlindEpistemicJudge, judge_proposal, sanitize_proposal_for_judge
from evolution.epistemic.quarantine import record_quarantined_claim, read_rejected_claims, check_prior_rejections
from evolution.epistemic.review_chamber import EpistemicReviewChamber, run_epistemic_review

__all__ = [
    "AdversarialCritic",
    "run_adversarial_critic",
    "EvidenceVerifier",
    "verify_epistemic_provenance",
    "validate_provenance",
    "AlternativeExplanationAgent",
    "run_alternative_explanation_agent",
    "BlindEpistemicJudge",
    "judge_proposal",
    "sanitize_proposal_for_judge",
    "record_quarantined_claim",
    "read_rejected_claims",
    "check_prior_rejections",
    "EpistemicReviewChamber",
    "run_epistemic_review",
]
