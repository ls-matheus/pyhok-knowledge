from __future__ import annotations

from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo


class BlindEpistemicJudge:
    """
    Blind Epistemic Judge (v2 - Multidimensional Epistemic Evaluation):
    Role: Adjudicate proposal validity, calculate multidimensional epistemic vector, and assign epistemic status based strictly on parallel isolated peer reviews.
    Principle of Blindness: Does NOT consume the Generator's self-assessed confidence or novelty scores.
    """

    def judge(
        self,
        proposal: dict[str, Any],
        critic_review: dict[str, Any],
        verifier_review: dict[str, Any],
        red_team_review: dict[str, Any] | None = None,
        memory_review: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Principle of Blindness: Explicitly filter out generator confidence and self-scores
        sanitized_proposal = {
            k: v for k, v in proposal.items()
            if k not in ("confidence", "novelty_score", "coverage_gain")
        }

        # 1. Extract reviews from parallel independent peers
        critic_passes = critic_review.get("passes_adversarial_check", False)
        critic_severity = critic_review.get("severity_score", 1.0)
        contradictions = critic_review.get("contradictions", [])
        challenges = critic_review.get("challenges", [])

        verifier_passes = verifier_review.get("passes_verification", False)
        circularity = verifier_review.get("circularity_detected", False)
        derivation_depth = verifier_review.get("derivation_depth", 1)
        independent_count = verifier_review.get("independent_evidence_count", 0)
        verifier_errors = verifier_review.get("errors", [])

        red_team = red_team_review or {}
        red_team_passes = red_team.get("passes_red_team_check", True)
        resistance_to_alternatives = red_team.get("resistance_to_alternatives", 1.0)
        parsimony_score = red_team.get("parsimony_score", 1.0)
        alternative_hypotheses = red_team.get("alternative_hypotheses", [])

        memory = memory_review or {}
        has_prior_rejection = memory.get("has_prior_rejection", False)
        repetition_warning = memory.get("repetition_warning")

        # 2. Compute Multidimensional Epistemic Vector
        evidence_strength = round(1.0 if verifier_passes else max(0.0, 1.0 - (len(verifier_errors) * 0.25)), 4)
        logical_consistency = round(max(0.0, 1.0 - critic_severity), 4)
        independence = round(min(1.0, independent_count / max(1, derivation_depth)), 4)
        alt_resistance = round(resistance_to_alternatives * parsimony_score, 4)
        provenance_integrity = 0.0 if circularity else 1.0

        epistemic_vector = {
            "evidence_strength": evidence_strength,
            "logical_consistency": logical_consistency,
            "independence": independence,
            "alternative_explanation_resistance": alt_resistance,
            "provenance_integrity": provenance_integrity,
        }

        composite_score = round(
            (evidence_strength * 0.25) +
            (logical_consistency * 0.25) +
            (independence * 0.15) +
            (alt_resistance * 0.15) +
            (provenance_integrity * 0.20),
            4
        )

        # 3. Categorical Decision Adjudication
        decision = "REJECT"
        quarantine_reason = None
        assigned_status = "SPECULATION"

        # Case 1: Fatal Epistemic Violations -> Immediate REJECT
        if circularity:
            decision = "REJECT"
            quarantine_reason = "FATAL_CIRCULARITY_DETECTED"
            assigned_status = "SPECULATION"
        elif has_prior_rejection:
            decision = "REJECT"
            quarantine_reason = f"REPEATS_PRIOR_REJECTED_CLAIM: {repetition_warning}"
            assigned_status = "SPECULATION"
        elif contradictions:
            decision = "REJECT"
            quarantine_reason = f"FATAL_KNOWLEDGE_CONTRADICTIONS: {', '.join(contradictions)}"
            assigned_status = "SPECULATION"
        elif critic_severity >= 0.50:
            decision = "REJECT"
            quarantine_reason = f"CRITIC_SEVERITY_TOO_HIGH ({critic_severity})"
            assigned_status = "SPECULATION"

        # Case 2: Deep Derivation, Confounders or Unresolved Challenges -> QUARANTINE
        elif derivation_depth > 3 and independent_count == 0:
            decision = "QUARANTINE"
            quarantine_reason = f"EXCEEDS_DERIVATION_DEPTH_LIMIT (depth={derivation_depth}, roots={independent_count})"
            assigned_status = "HYPOTHESIS"
        elif not verifier_passes:
            decision = "QUARANTINE"
            quarantine_reason = f"VERIFIER_UNRESOLVED_ERRORS: {', '.join(verifier_errors)}"
            assigned_status = "HYPOTHESIS"
        elif not red_team_passes or alt_resistance < 0.40:
            decision = "QUARANTINE"
            quarantine_reason = f"UNRESOLVED_ALTERNATIVE_EXPLANATIONS: {', '.join(alternative_hypotheses)}"
            assigned_status = "HYPOTHESIS"
        elif not critic_passes or challenges:
            decision = "QUARANTINE"
            quarantine_reason = f"UNRESOLVED_ADVERSARIAL_CHALLENGES: {', '.join(challenges)}"
            assigned_status = "HYPOTHESIS"

        # Case 3: Fully Approved -> ACCEPT
        else:
            decision = "ACCEPT"
            quarantine_reason = None
            assigned_status = "DERIVED" if derivation_depth > 0 else "HYPOTHESIS"

        return {
            "judge_role": "BLIND_EPISTEMIC_JUDGE",
            "decision": decision,
            "assigned_epistemic_status": assigned_status,
            "epistemic_vector": epistemic_vector,
            "epistemic_score": composite_score,
            "quarantine_reason": quarantine_reason,
            "derivation_depth": derivation_depth,
            "independent_evidence_count": independent_count,
            "critic_severity": critic_severity,
            "circularity_detected": circularity,
            "dissenting_challenges": challenges,
            "contradictions": contradictions,
            "alternative_hypotheses": alternative_hypotheses,
            "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
        }


def judge_proposal(
    proposal: dict[str, Any],
    critic_review: dict[str, Any],
    verifier_review: dict[str, Any],
    red_team_review: dict[str, Any] | None = None,
    memory_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    judge = BlindEpistemicJudge()
    return judge.judge(proposal, critic_review, verifier_review, red_team_review, memory_review)
