from __future__ import annotations

import math
import re
from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo


PROHIBITED_KEY_STEMS = {
    "confidence",
    "confidencescore",
    "noveltyscore",
    "novelty",
    "coveragegain",
    "coverage",
    "generatorscore",
    "generatorverdict",
    "selfassessment",
    "predictedmetrics",
    "internalweights",
    "modelconfidence",
    "generatorevaluation",
}


def _is_prohibited_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    normalized = re.sub(r"[^a-zA-Z0-9]", "", key).lower()
    return normalized in PROHIBITED_KEY_STEMS


def sanitize_proposal_for_judge(proposal: Any, _visited_ids: set[int] | None = None) -> Any:
    """
    Recursively and immutably purges all generator self-assessed metrics, weights, and scores.
    Handles arbitrary nesting, case-insensitivity, lists, dictionaries, and protects against cyclic object references.
    """
    if _visited_ids is None:
        _visited_ids = set()

    obj_id = id(proposal)
    if obj_id in _visited_ids:
        # Cyclic structure detected; break cycle gracefully
        return None
    _visited_ids.add(obj_id)

    try:
        if isinstance(proposal, dict):
            sanitized = {}
            for k, v in proposal.items():
                if _is_prohibited_key(k):
                    continue
                sanitized[k] = sanitize_proposal_for_judge(v, _visited_ids)
            return sanitized
        elif isinstance(proposal, list):
            return [sanitize_proposal_for_judge(item, _visited_ids) for item in proposal]
        return proposal
    finally:
        _visited_ids.remove(obj_id)


def _safe_float(val: Any, default: float = 0.0, min_val: float = 0.0, max_val: float = 1.0) -> float:
    try:
        if val is None or isinstance(val, bool):
            return default
        f = float(val)
        if not math.isfinite(f):
            return default
        return max(min_val, min(max_val, f))
    except (ValueError, TypeError):
        return default


class BlindEpistemicJudge:
    """
    Blind Epistemic Judge (v2.2):
    Role: Hierarchically adjudicate proposals, compute normalized epistemic vector, and assign categorical status.
    Principle of Absolute Blindness: Operates exclusively on recursively sanitized proposals, completely isolated from Generator self-assessed scores.
    """

    def judge(
        self,
        proposal: dict[str, Any] | None,
        critic_review: dict[str, Any] | None,
        verifier_review: dict[str, Any] | None,
        red_team_review: dict[str, Any] | None = None,
        memory_review: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Enforce Blindness: Recursively sanitize proposal
        sanitized = sanitize_proposal_for_judge(proposal) if isinstance(proposal, dict) else {}

        # 1. Normalize Inputs & Extract Reviewer Findings
        critic = critic_review if isinstance(critic_review, dict) else {}
        verifier = verifier_review if isinstance(verifier_review, dict) else {}
        red_team = red_team_review if isinstance(red_team_review, dict) else {}
        memory = memory_review if isinstance(memory_review, dict) else {}

        critic_passes = bool(critic.get("passes_adversarial_check", False))
        critic_severity = _safe_float(critic.get("severity_score", 1.0 if not critic_passes else 0.0))
        contradictions = critic.get("contradictions", []) if isinstance(critic.get("contradictions"), list) else []
        challenges = critic.get("challenges", []) if isinstance(critic.get("challenges"), list) else []

        verifier_passes = bool(verifier.get("passes_verification", False))
        circularity = bool(verifier.get("circularity_detected", False))
        derivation_depth = max(0, int(verifier.get("derivation_depth", 0))) if isinstance(verifier.get("derivation_depth"), int) else 0
        independent_count = max(0, int(verifier.get("independent_evidence_count", 0))) if isinstance(verifier.get("independent_evidence_count"), int) else 0
        verifier_errors = verifier.get("errors", []) if isinstance(verifier.get("errors"), list) else []
        eligible_for_derived = bool(verifier.get("eligible_for_derived_status", False))

        red_team_passes = bool(red_team.get("passes_red_team_check", False))
        resistance_to_alternatives = _safe_float(red_team.get("resistance_to_alternatives", 0.0))
        parsimony_score = _safe_float(red_team.get("parsimony_score", 0.0))
        alternative_hypotheses = red_team.get("alternative_hypotheses", []) if isinstance(red_team.get("alternative_hypotheses"), list) else []

        has_prior_rejection = bool(memory.get("has_prior_rejection", False))
        repetition_warning = memory.get("repetition_warning")

        # 2. Calculate Bounded Multidimensional Epistemic Tensor [0.0, 1.0]
        evidence_strength = _safe_float(
            verifier.get("evidence_strength_score"),
            default=(1.0 if verifier_passes else max(0.0, 1.0 - (len(verifier_errors) * 0.35)))
        )
        logical_consistency = _safe_float(
            critic.get("logical_consistency_score"),
            default=max(0.0, 1.0 - critic_severity)
        )
        independence = _safe_float(
            verifier.get("independence_score"),
            default=min(1.0, independent_count / max(1, derivation_depth))
        )
        alt_resistance = _safe_float(
            resistance_to_alternatives * parsimony_score,
            default=0.0
        )
        provenance_integrity = 0.0 if circularity else _safe_float(
            verifier.get("provenance_integrity_score"),
            default=1.0
        )

        epistemic_vector = {
            "evidence_strength": round(evidence_strength, 4),
            "logical_consistency": round(logical_consistency, 4),
            "independence": round(independence, 4),
            "alternative_explanation_resistance": round(alt_resistance, 4),
            "provenance_integrity": round(provenance_integrity, 4),
        }

        composite_score = round(
            (evidence_strength * 0.25) +
            (logical_consistency * 0.25) +
            (independence * 0.15) +
            (alt_resistance * 0.15) +
            (provenance_integrity * 0.20),
            4
        )
        composite_score = _safe_float(composite_score)

        # 3. Hierarchical Categorical Adjudication Rules
        decision = "REJECT"
        quarantine_reason = None
        assigned_status = "SPECULATION"

        # Tier 1: Fatal Epistemic Violations -> REJECT
        if not sanitized or not isinstance(sanitized, dict):
            decision = "REJECT"
            quarantine_reason = "NULL_OR_INVALID_PROPOSAL_PAYLOAD"
            assigned_status = "SPECULATION"
        elif circularity:
            decision = "REJECT"
            quarantine_reason = "FATAL_CIRCULARITY_DETECTED"
            assigned_status = "SPECULATION"
        elif has_prior_rejection and memory.get("match_type") in ("EXACT_MATCH", "TOKEN_PARAPHRASE", "STRUCTURAL_PARAPHRASE"):
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

        # Tier 2: Insufficient Grounding / Confounders / Overcomplexity -> QUARANTINE
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

        # Tier 3: Robustly Supported -> ACCEPT
        else:
            decision = "ACCEPT"
            quarantine_reason = None
            assigned_status = "DERIVED" if eligible_for_derived else "HYPOTHESIS"

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
            "sanitized_proposal_id": sanitized.get("proposal_id", sanitized.get("id", "prop_unknown")),
            "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
        }


def judge_proposal(
    proposal: dict[str, Any] | None,
    critic_review: dict[str, Any] | None,
    verifier_review: dict[str, Any] | None,
    red_team_review: dict[str, Any] | None = None,
    memory_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    judge = BlindEpistemicJudge()
    return judge.judge(proposal, critic_review, verifier_review, red_team_review, memory_review)
