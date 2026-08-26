from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
REJECTED_CLAIMS_FILE = ROOT / "evolution/rejected_claims.jsonl"


def record_quarantined_claim(
    proposal: dict[str, Any],
    judge_ruling: dict[str, Any],
    critic_review: dict[str, Any] | None = None,
    verifier_review: dict[str, Any] | None = None,
    cycle_id: str | None = None,
    file_path: Path = REJECTED_CLAIMS_FILE,
) -> dict[str, Any]:
    """
    Appends a quarantined or rejected proposition to the rejected claims registry.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)

    q_data = proposal.get("question", {}) or proposal
    entry = {
        "cycle_id": cycle_id or q_data.get("provenance", {}).get("cycle_id", "cycle_unknown"),
        "proposal_id": proposal.get("proposal_id", q_data.get("id", "prop_unknown")),
        "hypothesis": q_data.get("hypothesis", ""),
        "decision": judge_ruling.get("decision", "QUARANTINE"),
        "quarantine_reason": judge_ruling.get("quarantine_reason"),
        "assigned_epistemic_status": judge_ruling.get("assigned_epistemic_status", "SPECULATION"),
        "epistemic_score": judge_ruling.get("epistemic_score", 0.0),
        "challenges": critic_review.get("challenges", []) if critic_review else judge_ruling.get("dissenting_challenges", []),
        "contradictions": critic_review.get("contradictions", []) if critic_review else judge_ruling.get("contradictions", []),
        "recorded_at": datetime.now(ZoneInfo("UTC")).isoformat(),
    }

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

    return entry


def read_rejected_claims(file_path: Path = REJECTED_CLAIMS_FILE) -> list[dict[str, Any]]:
    """
    Reads all historical rejected and quarantined claims.
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
