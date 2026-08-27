from __future__ import annotations

import copy
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = ROOT / "scheduler/status.json"
POLICY_FILE = ROOT / "evolution/evolution-policy.json"

DEFAULT_STATUS = {
    "status": "IDLE",
    "current_cycle_id": None,
    "last_run": None,
    "last_success": None,
    "last_failure": None,
    "last_error": None,
    "last_stop_reason": None,
    "processed_proposals": [],
    "last_opportunity_id": None,
    "last_proposal_id": None,
    "last_question_id": None,
    "last_branch": None,
    "last_pr_url": None,
    "consecutive_failures": 0,
    "circuit_breaker": {
        "is_open": False,
        "max_consecutive_failures": 3,
        "tripped_at": None,
        "trip_reason": None
    },
    "audit_trail": {
        "main_before_sha": None,
        "proposal_commit_sha": None,
        "merge_commit_sha": None,
        "state_before_hash": None,
        "state_after_hash": None
    },
    "stats": {
        "total_runs": 0,
        "successful_runs": 0,
        "failed_runs": 0,
        "skipped_runs": 0,
        "blocked_runs": 0,
        "circuit_breaker_trips": 0
    }
}


def _get_now_iso(tz_name: str = "America/Sao_Paulo") -> str:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).isoformat()


def load_status(status_file: Path | None = None) -> dict[str, Any]:
    target_file = status_file or STATUS_FILE
    if not target_file.exists():
        return copy.deepcopy(DEFAULT_STATUS)
    try:
        data = json.loads(target_file.read_text(encoding="utf-8"))
        merged = copy.deepcopy(DEFAULT_STATUS)
        merged.update(data)

        stats = copy.deepcopy(DEFAULT_STATUS["stats"])
        if isinstance(data.get("stats"), dict):
            stats.update(data["stats"])
        merged["stats"] = stats

        cb = copy.deepcopy(DEFAULT_STATUS["circuit_breaker"])
        if isinstance(data.get("circuit_breaker"), dict):
            cb.update(data["circuit_breaker"])
        merged["circuit_breaker"] = cb

        at = copy.deepcopy(DEFAULT_STATUS["audit_trail"])
        if isinstance(data.get("audit_trail"), dict):
            at.update(data["audit_trail"])
        merged["audit_trail"] = at

        return merged
    except Exception:
        return copy.deepcopy(DEFAULT_STATUS)


def save_status(data: dict[str, Any], status_file: Path | None = None) -> None:
    target_file = status_file or STATUS_FILE
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_circuit_open(status_file: Path | None = None) -> tuple[bool, str | None]:
    current = load_status(status_file)
    cb = current.get("circuit_breaker", {})
    if cb.get("is_open", False):
        return True, cb.get("trip_reason", "consecutive_failures_exceeded")
    return False, None


def reset_circuit_breaker(status_file: Path | None = None) -> dict[str, Any]:
    current = load_status(status_file)
    current["consecutive_failures"] = 0
    current["circuit_breaker"]["is_open"] = False
    current["circuit_breaker"]["tripped_at"] = None
    current["circuit_breaker"]["trip_reason"] = None
    current["status"] = "IDLE"
    save_status(current, status_file)
    return current


def is_auto_merge_enabled() -> bool:
    """
    Checks kill switch for auto-merge. Defaults to False for safety (Shadow Mode).
    """
    env_val = os.getenv("AUTONOMOUS_MERGE_ENABLED", "").lower()
    return env_val in ("1", "true", "yes")


def start_cycle(cycle_id: str | None = None, status_file: Path | None = None) -> dict[str, Any]:
    current = load_status(status_file)
    now_str = _get_now_iso()
    if not cycle_id:
        cycle_id = f"cycle_{datetime.now(ZoneInfo('UTC')).strftime('%Y%m%d_%H%M%S')}"

    # Check circuit breaker
    if current.get("circuit_breaker", {}).get("is_open", False):
        current["status"] = "CIRCUIT_OPEN"
        save_status(current, status_file)
        raise RuntimeError(f"Circuit breaker is OPEN: {current['circuit_breaker'].get('trip_reason')}")

    current["status"] = "PREFLIGHT"
    current["current_cycle_id"] = cycle_id
    current["last_run"] = now_str
    current["last_error"] = None
    current["last_stop_reason"] = None
    current["stats"]["total_runs"] += 1
    save_status(current, status_file)
    return current


def update_phase(phase: str, metadata: dict[str, Any] | None = None, status_file: Path | None = None) -> dict[str, Any]:
    current = load_status(status_file)
    current["status"] = phase
    if metadata:
        for k, v in metadata.items():
            current[k] = v
    save_status(current, status_file)
    return current


def record_success(
    cycle_id: str | None = None,
    opportunity_id: str | None = None,
    proposal_id: str | None = None,
    question_id: str | None = None,
    branch: str | None = None,
    pr_url: str | None = None,
    stop_reason: str | None = None,
    audit_trail: dict[str, Any] | None = None,
    status_file: Path | None = None,
) -> dict[str, Any]:
    current = load_status(status_file)
    now_str = _get_now_iso()
    current["status"] = "IDLE"
    current["current_cycle_id"] = None
    current["last_success"] = now_str
    current["last_stop_reason"] = stop_reason or "cycle_completed_successfully"
    current["consecutive_failures"] = 0
    current["stats"]["successful_runs"] += 1

    if proposal_id:
        if "processed_proposals" not in current or not isinstance(current["processed_proposals"], list):
            current["processed_proposals"] = []
        if proposal_id not in current["processed_proposals"]:
            current["processed_proposals"].append(proposal_id)
        current["last_proposal_id"] = proposal_id

    if opportunity_id:
        current["last_opportunity_id"] = opportunity_id
    if question_id:
        current["last_question_id"] = question_id
    if branch:
        current["last_branch"] = branch
    if pr_url:
        current["last_pr_url"] = pr_url
    if audit_trail:
        current["audit_trail"].update(audit_trail)

    save_status(current, status_file)
    return current


def record_failure(
    error: str,
    stop_reason: str = "error",
    max_failures: int = 3,
    status_file: Path | None = None,
) -> dict[str, Any]:
    current = load_status(status_file)
    now_str = _get_now_iso()
    current["consecutive_failures"] += 1
    current["last_failure"] = now_str
    current["last_error"] = str(error)
    current["last_stop_reason"] = stop_reason
    current["current_cycle_id"] = None
    current["stats"]["failed_runs"] += 1

    # Trip circuit breaker if threshold exceeded
    if current["consecutive_failures"] >= max_failures:
        current["status"] = "CIRCUIT_OPEN"
        current["circuit_breaker"]["is_open"] = True
        current["circuit_breaker"]["tripped_at"] = now_str
        current["circuit_breaker"]["trip_reason"] = f"{current['consecutive_failures']} consecutive failures: {error}"
        current["stats"]["circuit_breaker_trips"] += 1
    else:
        current["status"] = "FAILED"

    save_status(current, status_file)
    return current


def record_skip(reason: str, status_file: Path | None = None) -> dict[str, Any]:
    current = load_status(status_file)
    current["status"] = "SKIPPED"
    current["current_cycle_id"] = None
    current["last_stop_reason"] = reason
    current["stats"]["skipped_runs"] += 1
    save_status(current, status_file)
    return current


def record_blocked(reason: str, status_file: Path | None = None) -> dict[str, Any]:
    current = load_status(status_file)
    current["status"] = "BLOCKED"
    current["current_cycle_id"] = None
    current["last_stop_reason"] = reason
    current["stats"]["blocked_runs"] += 1
    save_status(current, status_file)
    return current
