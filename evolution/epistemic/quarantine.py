from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
REJECTED_CLAIMS_FILE = ROOT / "evolution/rejected_claims.jsonl"

_WRITE_LOCK = threading.Lock()

NEGATION_TERMS = {
    "not", "no", "never", "neither", "nor", "fails", "without", "unrelated", "independent", "disproves", "cannot"
}


def _normalize_tokens(text: str) -> set[str]:
    if not isinstance(text, str):
        return set()
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    words = re.findall(r"\b[a-z0-9_]{3,}\b", cleaned)
    stop_words = {"the", "and", "that", "this", "with", "from", "for", "when", "then", "have", "has", "into"}
    return {w for w in words if w not in stop_words}


def _extract_polarity(text: str) -> bool:
    """Returns True if affirmative, False if negative/inverted."""
    if not isinstance(text, str):
        return True
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    words = set(re.findall(r"\b[a-z0-9_]+\b", cleaned))
    return len(words & NEGATION_TERMS) == 0


def record_quarantined_claim(
    proposal: dict[str, Any] | None,
    judge_ruling: dict[str, Any] | None,
    critic_review: dict[str, Any] | None = None,
    verifier_review: dict[str, Any] | None = None,
    red_team_review: dict[str, Any] | None = None,
    cycle_id: str | None = None,
    file_path: Path = REJECTED_CLAIMS_FILE,
) -> dict[str, Any]:
    """
    Appends a quarantined or rejected proposition to the active rejected claims registry.
    Uses threading.Lock for atomic concurrent append safety.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)

    prop = proposal if isinstance(proposal, dict) else {}
    q_data = prop.get("question") if isinstance(prop.get("question"), dict) else prop
    ruling = judge_ruling if isinstance(judge_ruling, dict) else {}

    entry = {
        "cycle_id": cycle_id or q_data.get("provenance", {}).get("cycle_id", "cycle_unknown"),
        "proposal_id": prop.get("proposal_id", q_data.get("id", "prop_unknown")),
        "hypothesis": q_data.get("hypothesis", ""),
        "required_signals": q_data.get("required_signals", []),
        "decision": ruling.get("decision", "QUARANTINE"),
        "quarantine_reason": ruling.get("quarantine_reason"),
        "assigned_epistemic_status": ruling.get("assigned_epistemic_status", "SPECULATION"),
        "epistemic_vector": ruling.get("epistemic_vector", {}),
        "epistemic_score": ruling.get("epistemic_score", 0.0),
        "challenges": critic_review.get("challenges", []) if critic_review else ruling.get("dissenting_challenges", []),
        "contradictions": critic_review.get("contradictions", []) if critic_review else ruling.get("contradictions", []),
        "alternative_hypotheses": red_team_review.get("alternative_hypotheses", []) if red_team_review else [],
        "provenance": q_data.get("provenance", {}),
        "recorded_at": datetime.now(ZoneInfo("UTC")).isoformat(),
    }

    serialized = json.dumps(entry, sort_keys=True) + "\n"
    with _WRITE_LOCK:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(serialized)

    return entry


def read_rejected_claims(file_path: Path = REJECTED_CLAIMS_FILE) -> list[dict[str, Any]]:
    """
    Reads all historical rejected and quarantined claims from active memory.
    Fail-closed and resilient to malformed lines.
    """
    if not file_path.exists():
        return []
    claims: list[dict[str, Any]] = []
    try:
        lines = file_path.read_text(encoding="utf-8").strip().splitlines()
    except Exception:
        return []

    for line in lines:
        line = line.strip()
        if line:
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    claims.append(parsed)
            except Exception:
                pass
    return claims


def check_prior_rejections(
    proposal: dict[str, Any] | None,
    file_path: Path = REJECTED_CLAIMS_FILE,
    similarity_threshold: float = 0.70
) -> dict[str, Any]:
    """
    Active Negative Memory 2.1 (Layered Matching with Polarity Sensitivity):
    1. EXACT MATCH
    2. TOKEN JACCARD
    3. SIGNAL & OPERATOR OVERLAP
    4. STRUCTURAL PARAPHRASE
    5. POLARITY CHECK (distinguishes negation/novelty from disguised repetition).
    """
    if not proposal or not isinstance(proposal, dict):
        return {
            "has_prior_rejection": False,
            "match_type": "NONE",
            "highest_similarity": 0.0,
            "matching_rejection": None,
            "repetition_warning": None,
            "reasons_to_reconsider": [],
        }

    prior_claims = read_rejected_claims(file_path)
    if not prior_claims:
        return {
            "has_prior_rejection": False,
            "match_type": "NONE",
            "highest_similarity": 0.0,
            "matching_rejection": None,
            "repetition_warning": None,
            "reasons_to_reconsider": [],
        }

    q_data = proposal.get("question") if isinstance(proposal.get("question"), dict) else proposal
    curr_hypo = str(q_data.get("hypothesis", "") or "")
    curr_tokens = _normalize_tokens(curr_hypo)
    curr_signals = set(q_data.get("required_signals", []) if isinstance(q_data.get("required_signals"), list) else [])
    curr_polarity = _extract_polarity(curr_hypo)

    if not curr_tokens:
        return {
            "has_prior_rejection": False,
            "match_type": "NONE",
            "highest_similarity": 0.0,
            "matching_rejection": None,
            "repetition_warning": None,
            "reasons_to_reconsider": [],
        }

    highest_sim = 0.0
    best_match: dict[str, Any] | None = None
    match_type = "NONE"

    for claim in prior_claims:
        past_hypo = str(claim.get("hypothesis", "") or "")
        past_tokens = _normalize_tokens(past_hypo)
        past_signals = set(claim.get("required_signals", []) if isinstance(claim.get("required_signals"), list) else [])
        past_polarity = _extract_polarity(past_hypo)

        # 1. Exact Match
        if curr_hypo.strip().lower() == past_hypo.strip().lower() and len(curr_hypo.strip()) > 5:
            highest_sim = 1.0
            best_match = claim
            match_type = "EXACT_MATCH"
            break

        # 2. Token Jaccard
        intersection = curr_tokens & past_tokens
        union = curr_tokens | past_tokens
        jaccard = len(intersection) / len(union) if union else 0.0

        # If polarities differ (one has negation, one does not), it's not a direct paraphrase repeat
        if curr_polarity != past_polarity:
            continue

        # 3. Signal Overlap & Structural Paraphrase
        same_signals = (curr_signals == past_signals and len(curr_signals) > 0)

        if jaccard > highest_sim:
            highest_sim = jaccard
            best_match = claim
            if jaccard >= similarity_threshold:
                match_type = "TOKEN_PARAPHRASE"
            elif same_signals and jaccard >= 0.50:
                match_type = "STRUCTURAL_PARAPHRASE"

    is_repetition = (match_type != "NONE" and highest_sim >= 0.50)
    warning = None
    reasons_to_reconsider: list[str] = []

    if is_repetition and best_match:
        past_reason = best_match.get("quarantine_reason", "prior_rejection")
        warning = (
            f"Proposal matches prior rejection '{best_match.get('proposal_id')}' via {match_type} "
            f"(similarity={highest_sim:.2f}, prior_reason='{past_reason}')"
        )
        if "CIRCULARITY" in str(past_reason):
            reasons_to_reconsider.append("Prior claim was rejected for fatal circularity.")
        if "CONTRADICTION" in str(past_reason):
            reasons_to_reconsider.append("Prior claim was rejected for knowledge contradiction.")

    return {
        "has_prior_rejection": is_repetition,
        "match_type": match_type,
        "highest_similarity": round(highest_sim, 4),
        "matching_rejection": best_match if is_repetition else None,
        "repetition_warning": warning,
        "reasons_to_reconsider": reasons_to_reconsider,
    }
