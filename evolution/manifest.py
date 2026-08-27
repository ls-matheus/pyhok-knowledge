from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS_DIR = ROOT / "evolution/manifests"


def create_cycle_manifest(
    cycle_id: str,
    main_before_sha: str,
    state_before_hash: str,
    state_after_hash: str,
    proposal_hash: str,
    dataset_counts_before: dict[str, int],
    dataset_counts_after: dict[str, int],
    predicted_metrics: dict[str, float],
    observed_metrics: dict[str, Any],
    gate_verdict: dict[str, Any],
    action_taken: str,
    timestamp_start: str,
    timestamp_end: str | None = None,
    manifests_dir: Path = MANIFESTS_DIR,
) -> dict[str, Any]:
    """
    Creates an immutable, fully reproducible atomic manifest for an evolution cycle.
    """
    if timestamp_end is None:
        timestamp_end = datetime.now(ZoneInfo("UTC")).isoformat()

    manifests_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = manifests_dir / f"manifest_{cycle_id}.json"

    manifest_data = {
        "cycle_id": cycle_id,
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
        "main_before_sha": main_before_sha,
        "state_before_hash": state_before_hash,
        "state_after_hash": state_after_hash,
        "proposal_hash": proposal_hash,
        "dataset_counts_before": dataset_counts_before,
        "dataset_counts_after": dataset_counts_after,
        "predicted_metrics": predicted_metrics,
        "observed_metrics": observed_metrics,
        "gate_verdict": gate_verdict,
        "action_taken": action_taken,
    }

    manifest_file.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_data
