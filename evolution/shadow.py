from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

from evolution.ledger import (
    hash_knowledge_state,
    hash_proposal,
    append_ledger_event,
    LEDGER_FILE,
)


def record_shadow_candidate(
    cycle_id: str,
    proposal_data: dict[str, Any],
    initial_state_hash: str | None = None,
    resulting_state_hash: str | None = None,
    ledger_path: Path = LEDGER_FILE,
) -> dict[str, Any]:
    """
    Records a proposed evolution in the immutable Evolution Ledger under Shadow Mode without authorizing auto-merge.
    """
    if initial_state_hash is None:
        initial_state_hash = hash_knowledge_state()

    proposal_payload = proposal_data.get("proposal", {})
    proposal_id = proposal_payload.get("proposal_id", "prop_unknown")
    prop_hash = hash_proposal(proposal_payload)

    if resulting_state_hash is None:
        # In shadow mode, compute resulting state hash
        resulting_state_hash = initial_state_hash

    predictions = {
        "novelty_score": float(proposal_payload.get("novelty_score", 0.85)),
        "coverage_gain": float(proposal_payload.get("coverage_gain", 0.20)),
        "confidence": float(proposal_payload.get("confidence", 0.90)),
    }

    # Classification based on initial heuristics
    confidence = predictions["confidence"]
    novelty = predictions["novelty_score"]

    if confidence >= 0.80 and novelty >= 0.70:
        classification = "PREDICTED_IMPROVEMENT"
    elif confidence < 0.60:
        classification = "PREDICTED_REGRESSION"
    else:
        classification = "PREDICTED_NEUTRAL"

    event = {
        "cycle_id": cycle_id,
        "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
        "previous_event_hash": None,  # Will be auto-computed by append_ledger_event
        "initial_state_hash": initial_state_hash,
        "proposal_hash": prop_hash,
        "resulting_state_hash": resulting_state_hash,
        "proposal_id": proposal_id,
        "predictions": predictions,
        "gate_verdict": {
            "valid": True,
            "safe": True,
            "classification": classification,
        },
        "action_taken": "SHADOW_RECORDED",
        "post_evaluation": None,
    }

    recorded = append_ledger_event(event, ledger_path=ledger_path)
    print(f"[SHADOW] Candidate '{proposal_id}' recorded in Evolution Ledger ({recorded['cycle_id']}).")
    print(f"[SHADOW] Classification: {classification} (confidence: {confidence:.2f}, novelty: {novelty:.2f}).")
    print("[MERGE] DISABLED_SHADOW_MODE: Automatic merge not authorized in observation mode.")
    return recorded
