"""
PyHok Epistemic Multi-Agent Architecture
Separation of duties: Generator -> Adversarial Critic + Evidence Verifier -> Blind Judge.
"""
from evolution.epistemic.critic import AdversarialCritic, run_adversarial_critic
from evolution.epistemic.verifier import EvidenceVerifier, verify_epistemic_provenance
from evolution.epistemic.judge import BlindEpistemicJudge, judge_proposal
from evolution.epistemic.quarantine import record_quarantined_claim, read_rejected_claims
from evolution.epistemic.review_chamber import EpistemicReviewChamber, run_epistemic_review

__all__ = [
    "AdversarialCritic",
    "run_adversarial_critic",
    "EvidenceVerifier",
    "verify_epistemic_provenance",
    "BlindEpistemicJudge",
    "judge_proposal",
    "record_quarantined_claim",
    "read_rejected_claims",
    "EpistemicReviewChamber",
    "run_epistemic_review",
]
