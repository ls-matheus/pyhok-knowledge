import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASELINE_FILE = ROOT / "evolution/baseline.json"
LEDGER_FILE = ROOT / "evolution/ledger.jsonl"
MANIFESTS_DIR = ROOT / "evolution/manifests"
EVALUATIONS_FILE = ROOT / "evolution/post_evaluations.jsonl"

from evolution.baseline import verify_baseline_integrity
from evolution.ledger import verify_ledger_integrity, read_ledger_events, compute_sha256, hash_proposal


def verify_cycle_manifest_integrity(
    manifest_data: dict[str, Any],
    ledger_events: list[dict[str, Any]] | None = None,
) -> tuple[bool, list[str]]:
    """
    Verifies that a cycle manifest satisfies all Measurement Integrity Gate 2.0 constraints.
    """
    errors: list[str] = []
    cycle_id = manifest_data.get("cycle_id")
    if not cycle_id:
        errors.append("MANIFEST_ERROR: missing cycle_id")
        return False, errors

    # Check required fields
    required_fields = [
        "timestamp_start",
        "timestamp_end",
        "main_before_sha",
        "state_before_hash",
        "state_after_hash",
        "proposal_hash",
        "dataset_counts_before",
        "dataset_counts_after",
        "predicted_metrics",
        "observed_metrics",
        "gate_verdict",
        "action_taken",
    ]
    for rf in required_fields:
        if rf not in manifest_data:
            errors.append(f"MANIFEST_ERROR ({cycle_id}): missing field '{rf}'")

    # Check dataset counts are non-negative ints
    for when in ("dataset_counts_before", "dataset_counts_after"):
        counts = manifest_data.get(when, {})
        if not isinstance(counts, dict):
            errors.append(f"MANIFEST_ERROR ({cycle_id}): {when} is not a dictionary")
        else:
            for k in ("questions", "signals", "relations"):
                if k not in counts or not isinstance(counts[k], int) or counts[k] < 0:
                    errors.append(f"MANIFEST_ERROR ({cycle_id}): {when}['{k}'] is invalid")

    # Check observed metrics
    obs = manifest_data.get("observed_metrics", {})
    if not isinstance(obs, dict) or not obs:
        errors.append(f"MANIFEST_ERROR ({cycle_id}): observed_metrics is empty or invalid")
    else:
        for metric in ("novelty", "coverage_gain", "domain_coverage_delta", "signal_coverage_delta", "redundancy"):
            if metric in obs:
                val = obs[metric]
                if not isinstance(val, (int, float)) or not (0.0 <= val <= 1.0):
                    errors.append(f"MANIFEST_ERROR ({cycle_id}): observed_metrics['{metric}'] out of range [0, 1]")

    # Check ledger correspondence if ledger events are provided
    if ledger_events:
        matching_event = next((e for e in ledger_events if e.get("cycle_id") == cycle_id), None)
        if matching_event is None:
            errors.append(f"MANIFEST_ERROR ({cycle_id}): no matching event in ledger")
        else:
            if manifest_data.get("state_before_hash") != matching_event.get("initial_state_hash"):
                errors.append(f"MANIFEST_ERROR ({cycle_id}): state_before_hash does not match ledger initial_state_hash")
            if manifest_data.get("state_after_hash") != matching_event.get("resulting_state_hash"):
                errors.append(f"MANIFEST_ERROR ({cycle_id}): state_after_hash does not match ledger resulting_state_hash")
            if manifest_data.get("proposal_hash") != matching_event.get("proposal_hash"):
                errors.append(f"MANIFEST_ERROR ({cycle_id}): proposal_hash does not match ledger proposal_hash")

    return len(errors) == 0, errors


def verify_measurement_integrity(
    baseline_path: Path = BASELINE_FILE,
    ledger_path: Path = LEDGER_FILE,
    manifests_dir: Path = MANIFESTS_DIR,
) -> tuple[bool, dict[str, Any], list[str]]:
    """
    Measurement Integrity Gate 2.0: Full cryptographic and epistemic validation of the longitudinal experiment.
    """
    all_errors: list[str] = []

    # 1. Baseline Integrity
    baseline_ok, baseline_msg = verify_baseline_integrity(baseline_path)
    if not baseline_ok:
        all_errors.append(f"MEASUREMENT_GATE: {baseline_msg}")

    # 2. Ledger Integrity
    ledger_ok, ledger_errors = verify_ledger_integrity(ledger_path)
    if not ledger_ok:
        all_errors.extend(ledger_errors)

    ledger_events = read_ledger_events(ledger_path) if ledger_path.exists() else []
    manifest_files = list(manifests_dir.glob("manifest_*.json")) if manifests_dir.exists() else []

    verified_manifests = 0
    for mf in manifest_files:
        try:
            m_data = json.loads(mf.read_text(encoding="utf-8"))
            m_ok, m_errors = verify_cycle_manifest_integrity(m_data, ledger_events=ledger_events)
            if not m_ok:
                all_errors.extend(m_errors)
            else:
                verified_manifests += 1
        except Exception as exc:
            all_errors.append(f"MANIFEST_ERROR ({mf.name}): cannot read JSON - {exc}")

    is_valid = len(all_errors) == 0
    summary = {
        "status": "PASS" if is_valid else "FAIL",
        "baseline_integrity": "VALID" if baseline_ok else "INVALID",
        "ledger_integrity": "VALID" if ledger_ok else "INVALID",
        "total_ledger_events": len(ledger_events),
        "total_manifests": len(manifest_files),
        "verified_manifests": verified_manifests,
        "errors": all_errors,
    }
    return is_valid, summary, all_errors


def main() -> int:
    is_valid, summary, errors = verify_measurement_integrity()
    print(json.dumps(summary, indent=2))
    if not is_valid:
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
