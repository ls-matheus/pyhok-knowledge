from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
REJECTED_CLAIMS_FILE = ROOT / "evolution/rejected_claims.jsonl"


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"\b[a-z0-9_]{3,}\b", text.lower())
    return set(words)


def record_quarantined_claim(
    proposal: dict[str, Any],
    judge_ruling: dict[str, Any],
    critic_review: dict[str, Any] | None = None,
    verifier_review: dict[str, Any] | None = None,
    red_team_review: dict[str, Any] | None = None,
    cycle_id: str | None = None,
    file_path: Path = REJECTED_CLAIMS_FILE,
) -> dict[str, Any]:
    """
    Appends a quarantined or rejected proposition to the active rejected claims registry.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)

    q_data = proposal.get("question", {}) or proposal
    entry = {
        "cycle_id": cycle_id or q_data.get("provenance", {}).get("cycle_id", "cycle_unknown"),
        "proposal_id": proposal.get("proposal_id", q_data.get("id", "prop_unknown")),
        "hypothesis": q_data.get("hypothesis", ""),
        "required_signals": q_data.get("required_signals", []),
        "decision": judge_ruling.get("decision", "QUARANTINE"),
        "quarantine_reason": judge_ruling.get("quarantine_reason"),
        "assigned_epistemic_status": judge_ruling.get("assigned_epistemic_status", "SPECULATION"),
        "epistemic_vector": judge_ruling.get("epistemic_vector", {}),
        "challenges": critic_review.get("challenges", []) if critic_review else judge_ruling.get("dissenting_challenges", []),
        "contradictions": critic_review.get("contradictions", []) if critic_review else judge_ruling.get("contradictions", []),
        "alternative_hypotheses": red_team_review.get("alternative_hypotheses", []) if red_team_review else [],
        "recorded_at": datetime.now(ZoneInfo("UTC")).isoformat(),
    }

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

    return entry


def read_rejected_claims(file_path: Path = REJECTED_CLAIMS_FILE) -> list[dict[str, Any]]:
    """
    Reads all historical rejected and quarantined claims from active memory.
    """
    if not file_path.exists():
        return []
    claims: list[dict[str, Any]] = []
    for line in file_path.read_text(encoding="utf-8").strip().splitlines():
        line = line.strip()
        if line:
            try:
                claims.append(json.loads(line))
            except Exception:
                pass
    return claims


def check_prior_rejections(
    proposal: dict[str, Any],
    file_path: Path = REJECTED_CLAIMS_FILE,
    similarity_threshold: float = 0.70
) -> dict[str, Any]:
    """
    Active Negative Memory:
    Checks whether this proposal is a disguised repeat of a previously rejected hypothesis.
    Returns: is_repetition (bool), matching_rejections (list), highest_similarity (float).
    """
    prior_claims = read_rejected_claims(file_path)
    if not prior_claims:
        return {
            "has_prior_rejection": False,
            "highest_similarity": 0.0,
            "matching_rejection": None,
            "repetition_warning": None,
        }

    q_data = proposal.get("question", {}) or proposal
    curr_hypo = q_data.get("hypothesis", "")
    curr_tokens = _tokenize(curr_hypo)
    if not curr_tokens:
        return {
            "has_prior_rejection": False,
            "highest_similarity": 0.0,
            "matching_rejection": None,
            "repetition_warning": None,
        }

    highest_sim = 0.0
    best_match: dict[str, Any] | None = None

    for claim in prior_claims:
        past_hypo = claim.get("hypothesis", "")
        past_tokens = _tokenize(past_hypo)
        if not past_tokens:
            continue
        intersection = curr_tokens & past_tokens
        union = curr_tokens | past_tokens
        jaccard = len(intersection) / len(union) if union else 0.0

        if jaccard > highest_sim:
            highest_sim = jaccard
            best_match = claim

    is_repetition = highest_sim >= similarity_threshold
    warning = None
    if is_repetition and best_match:
        warning = (
            f"Proposal matches previously rejected claim '{best_match.get('proposal_id')}' "
            f"(similarity={highest_sim:.2f}, reason='{best_match.get('quarantine_reason')}')"
        )

    return {
        "has_prior_rejection": is_repetition,
        "highest_similarity": round(highest_sim, 4),
        "matching_rejection": best_match if is_repetition else None,
        "repetition_warning": warning,
    }
