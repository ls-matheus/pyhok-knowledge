from __future__ import annotations

from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo


class BlindEpistemicJudge:
    """
    Blind Epistemic Judge:
    Role: Adjudicate proposal validity and assign epistemic status based strictly on Adversarial Critic and Evidence Verifier reviews.
    Principle of Blindness: Does NOT consume the Generator's self-assessed confidence or novelty scores.
    """

    def judge(
        self,
        proposal: dict[str, Any],
        critic_review: dict[str, Any],
        verifier_review: dict[str, Any]
    ) -> dict[str, Any]:
        # Principle of Blindness: Filter out generator confidence and self-scores
        sanitized_proposal = {k: v for k, v in proposal.items() if k not in ("confidence", "novelty_score", "coverage_gain")}

        critic_passes = critic_review.get("passes_adversarial_check", False)
        critic_severity = critic_review.get("severity_score", 1.0)
        contradictions = critic_review.get("contradictions", [])
        challenges = critic_review.get("challenges", [])

        verifier_passes = verifier_review.get("passes_verification", False)
        circularity = verifier_review.get("circularity_detected", False)
        derivation_depth = verifier_review.get("derivation_depth", 1)
        independent_count = verifier_review.get("independent_evidence_count", 0)
        verifier_errors = verifier_review.get("errors", [])

        decision = "REJECT"
        quarantine_reason = None
        assigned_status = "SPECULATION"
        epistemic_score = 0.0

        # Case 1: Fatal Epistemic Violations -> Immediate REJECT
        if circularity:
            decision = "REJECT"
            quarantine_reason = "FATAL_CIRCULARITY_DETECTED"
            assigned_status = "SPECULATION"
            epistemic_score = 0.0
        elif contradictions:
            decision = "REJECT"
            quarantine_reason = "FATAL_KNOWLEDGE_CONTRADICTION"
            assigned_status = "SPECULATION"
            epistemic_score = 0.10
        elif critic_severity >= 0.50:
            decision = "REJECT"
            quarantine_reason = f"CRITIC_SEVERITY_TOO_HIGH ({critic_severity})"
            assigned_status = "SPECULATION"
            epistemic_score = 0.20

        # Case 2: Deep Derivation or Minor Weakness -> QUARANTINE
        elif derivation_depth > 3 and independent_count == 0:
            decision = "QUARANTINE"
            quarantine_reason = f"EXCEEDS_DERIVATION_DEPTH_LIMIT (depth={derivation_depth}, roots={independent_count})"
            assigned_status = "HYPOTHESIS"
            epistemic_score = 0.45
        elif not verifier_passes:
            decision = "QUARANTINE"
            quarantine_reason = f"VERIFIER_UNRESOLVED_ERRORS: {', '.join(verifier_errors)}"
            assigned_status = "HYPOTHESIS"
            epistemic_score = 0.50
        elif not critic_passes or challenges:
            decision = "QUARANTINE"
            quarantine_reason = f"UNRESOLVED_ADVERSARIAL_CHALLENGES: {', '.join(challenges)}"
            assigned_status = "HYPOTHESIS"
            epistemic_score = 0.60

        # Case 3: Fully Approved -> ACCEPT
        else:
            decision = "ACCEPT"
            quarantine_reason = None
            assigned_status = "DERIVED" if derivation_depth > 0 else "HYPOTHESIS"
            epistemic_score = round(1.0 - (critic_severity * 0.5), 4)

        return {
            "judge_role": "BLIND_EPISTEMIC_JUDGE",
            "decision": decision,
            "assigned_epistemic_status": assigned_status,
            "epistemic_score": epistemic_score,
            "quarantine_reason": quarantine_reason,
            "derivation_depth": derivation_depth,
            "independent_evidence_count": independent_count,
            "critic_severity": critic_severity,
            "circularity_detected": circularity,
            "dissenting_challenges": challenges,
            "contradictions": contradictions,
            "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
        }


def judge_proposal(
    proposal: dict[str, Any],
    critic_review: dict[str, Any],
    verifier_review: dict[str, Any]
) -> dict[str, Any]:
    judge = BlindEpistemicJudge()
    return judge.judge(proposal, critic_review, verifier_review)
